"""Random Forest classifier pipeline for dataset_validated.csv

Steps implemented:
- Load CSV
- Build a composite `trend_score` and binary `success` target using a threshold
- Select features
- Drop NA rows
- Train/test split
- Train RandomForestClassifier
- Evaluate (accuracy, confusion matrix, classification report)
- Print feature importances

Adjustable params: THRESHOLD, N_ESTIMATORS, MAX_DEPTH, TEST_SIZE
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report


CSV_PATH = os.path.join(os.path.dirname(__file__), "dataset_validated.csv")

# Parameters (tweakable)
THRESHOLD = None  # if None we'll set it to the median of trend_score
TEST_SIZE = 0.2
RANDOM_STATE = 42
N_ESTIMATORS = 200
MAX_DEPTH = 10


def load_data(path=CSV_PATH):
    df = pd.read_csv(path)
    return df


def build_target(df, threshold=None):
    # Build a FUTURE growth based target to avoid data leakage.
    # future_growth = trends_last_value - trends_first_value
    df = df.copy()

    # Ensure numeric
    for col in ["trends_last_value", "trends_first_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    future_growth = None
    if ("trends_last_value" in df.columns) and ("trends_first_value" in df.columns):
        future_growth = df["trends_last_value"] - df["trends_first_value"]
    else:
        # fallback: if not present, create zero growth
        future_growth = pd.Series(np.zeros(len(df)), index=df.index)

    df["future_growth"] = future_growth

    # automatic threshold on future growth: use top 25% (more selective)
    if threshold is None:
        threshold = df["future_growth"].quantile(0.75)

    df["success"] = (df["future_growth"] >= threshold).astype(int)
    return df, threshold


def prepare_features(df):
    # Use only current / initial signals (no future columns like trends_last_value or future_growth)
    features = [
        "trends_mean",
        "trends_std",
        "trends_slope",
        "yt_total_views",
        "yt_total_likes",
        "yt_total_comments",
        "yt_videos_count",
        "ali_avg_sale_price",
        "ali_avg_evaluate_rate",
        "ali_total_orders",
        # derived features may be present already
        "yt_engagement_rate",
        "price_per_order",
        # new derived features
        "views_per_video",
        "comment_rate",
        "orders_per_price",
    ]

    # Keep only available features
    available = [f for f in features if f in df.columns]
    X = df[available].copy()
    y = df["success"].copy()

    # Drop rows with NA in X or y
    df_xy = pd.concat([X, y], axis=1)
    df_xy = df_xy.dropna()

    X = df_xy[available]
    y = df_xy["success"]
    return X, y, available


def train_and_evaluate(X, y):
    # Use TimeSeriesSplit to avoid data leakage: train on past, test on future
    # fewer folds to keep each fold reasonably sized
    tscv = TimeSeriesSplit(n_splits=3)

    aucs = []
    accs = []
    cms = []
    crs = []

    last_model = None
    # iterate folds
    for fold, (train_index, test_index) in enumerate(tscv.split(X)):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(X_test)[:, 1]
        else:
            y_proba = y_pred.astype(float)

        # metrics for this fold
        try:
            auc = roc_auc_score(y_test, y_proba)
        except Exception:
            auc = float("nan")

        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)
        cr = classification_report(y_test, y_pred)

        aucs.append(auc)
        accs.append(acc)
        cms.append(cm)
        crs.append(cr)

        last_model = model
        last_X_test = X_test
        last_y_test = y_test
        last_y_pred = y_pred
        last_y_proba = y_proba

    # Aggregate metrics (use last fold for detailed outputs)
    mean_auc = np.nanmean(aucs)
    mean_acc = float(np.mean(accs))

    # Combine confusion matrices by summing
    total_cm = None
    for m in cms:
        if total_cm is None:
            total_cm = m
        else:
            total_cm = total_cm + m

    # classification report: keep last fold report for display
    last_cr = crs[-1] if crs else ""

    return last_model, mean_acc, total_cm, last_cr, last_X_test, last_y_test, last_y_pred, last_y_proba, mean_auc


def main():
    print("Loading data from:", CSV_PATH)
    df = load_data(CSV_PATH)

    # Ensure generated_at is datetime for temporal sorting
    if "generated_at" in df.columns:
        df["generated_at"] = pd.to_datetime(df["generated_at"], errors="coerce")
        df = df.sort_values(by="generated_at").reset_index(drop=True)

    # Derived features (only use past/initial signals)
    # yt_engagement_rate = (likes+comments)/(views+1)
    if all(c in df.columns for c in ["yt_total_likes", "yt_total_comments", "yt_total_views"]):
        df["yt_engagement_rate"] = (
            (pd.to_numeric(df["yt_total_likes"], errors="coerce").fillna(0)
             + pd.to_numeric(df["yt_total_comments"], errors="coerce").fillna(0))
            / (pd.to_numeric(df["yt_total_views"], errors="coerce").fillna(0) + 1)
        )

    # trend_growth_rate = (last - first)/(first + 1)  (for analysis only, not as feature if it's future)
    if all(c in df.columns for c in ["trends_last_value", "trends_first_value"]):
        df["trend_growth_rate"] = (
            (pd.to_numeric(df["trends_last_value"], errors="coerce").fillna(0)
             - pd.to_numeric(df["trends_first_value"], errors="coerce").fillna(0))
            / (pd.to_numeric(df["trends_first_value"], errors="coerce").fillna(0) + 1)
        )

    # price_per_order = ali_avg_sale_price / (ali_total_orders + 1)
    if "ali_avg_sale_price" in df.columns and "ali_total_orders" in df.columns:
        df["price_per_order"] = pd.to_numeric(df["ali_avg_sale_price"], errors="coerce").fillna(0) / (
            pd.to_numeric(df["ali_total_orders"], errors="coerce").fillna(0) + 1
        )

    # Feature 1 - views per video
    if "yt_total_views" in df.columns and "yt_videos_count" in df.columns:
        df["views_per_video"] = (
            pd.to_numeric(df["yt_total_views"], errors="coerce").fillna(0)
            / (pd.to_numeric(df["yt_videos_count"], errors="coerce").fillna(0) + 1)
        )

    # Feature 2 - comment rate
    if "yt_total_comments" in df.columns and "yt_total_views" in df.columns:
        df["comment_rate"] = (
            pd.to_numeric(df["yt_total_comments"], errors="coerce").fillna(0)
            / (pd.to_numeric(df["yt_total_views"], errors="coerce").fillna(0) + 1)
        )

    # Feature 3 - orders per price
    if "ali_total_orders" in df.columns and "ali_avg_sale_price" in df.columns:
        df["orders_per_price"] = (
            pd.to_numeric(df["ali_total_orders"], errors="coerce").fillna(0)
            / (pd.to_numeric(df["ali_avg_sale_price"], errors="coerce").fillna(0) + 1)
        )

    print("Building target (trend_score)...")
    df, used_threshold = build_target(df, threshold=THRESHOLD)
    print(f"Using threshold={used_threshold:.4f}")

    print("Preparing features and cleaning NAs...")
    X, y, feature_names = prepare_features(df)
    print(f"Features used ({len(feature_names)}): {feature_names}")
    print(f"Final dataset size: {X.shape[0]} rows")

    if X.shape[0] < 10:
        print("Warning: very few rows after cleaning - model may not be reliable.")

    print("Training Random Forest (TimeSeriesSplit)...")
    (
        model,
        acc,
        cm,
        cr,
        X_test,
        y_test,
        y_pred,
        y_proba,
        mean_auc,
    ) = train_and_evaluate(X, y)

    print("\n=== Evaluation (aggregated across folds) ===")
    print(f"Mean Accuracy: {acc:.4f}")
    try:
        print(f"Mean ROC AUC: {mean_auc:.4f}")
    except Exception:
        pass
    print("Confusion Matrix (summed across folds):\n", cm)
    print("Classification Report (last fold):\n", cr)

    # =========================
    # TREND PREDICTIONS
    # =========================

    results = X_test.copy()
    results["prediction"] = y_pred
    results["probability"] = y_proba

    # Recover original metadata (keyword, category_name)
    if "keyword" in df.columns:
        results["keyword"] = df.loc[X_test.index, "keyword"].values

    if "category_name" in df.columns:
        results["category_name"] = df.loc[X_test.index, "category_name"].values

    # Sort by highest probability
    results = results.sort_values(by="probability", ascending=False)

    print("\n=== TOP TRENDING KEYWORDS ===")
    cols_to_show = [c for c in ["keyword", "probability"] if c in results.columns]
    print(results[cols_to_show].head(20))

    # =========================
    # CATEGORY ANALYSIS
    # =========================
    if "category_name" in results.columns:
        category_scores = (
            results.groupby("category_name")["probability"].mean().sort_values(ascending=False)
        )

        print("\n=== TOP CATEGORIES ===")
        print(category_scores.head(10))

    # Filter to strong predictions (probability >= 0.8)
    filtered = results[results["probability"] >= 0.80]

    # Save top predictions (cleaned)
    out_csv = os.path.join(os.path.dirname(__file__), "top_predictions.csv")

    final_cols = [
        c for c in [
            "keyword",
            "category_name",
            "probability",
            "prediction",
        ] if c in filtered.columns
    ]

    final_df = filtered[final_cols]
    final_df.to_csv(out_csv, index=False)
    print(f"Top predictions (filtered >=0.80) saved to: {out_csv}")

    # Feature importances (align with feature_names)
    importances = model.feature_importances_
    fi = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    print("\nFeature importances:")
    for name, imp in fi:
        print(f"  {name}: {imp:.4f}")

    # Save model and optionally the processed dataframe
    model_path = os.path.join(os.path.dirname(__file__), "rf_model.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved to: {model_path}")


if __name__ == "__main__":
    main()
