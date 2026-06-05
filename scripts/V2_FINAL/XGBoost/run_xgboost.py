import os
import argparse
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import classification_report, mean_squared_error, f1_score, precision_score, recall_score, roc_auc_score
import joblib

try:
    from xgboost import XGBClassifier, XGBRegressor
    from xgboost.sklearn import XGBRanker
except Exception:
    # xgboost might not be installed in the environment running static checks
    XGBClassifier = None
    XGBRegressor = None
    XGBRanker = None


DEFAULT_DATA = "dataset_validated.csv"


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def compute_engagement_rate(df: pd.DataFrame) -> pd.Series:
    # engagement = (likes + comments) / views
    likes = df.get("yt_total_likes", 0).fillna(0)
    comments = df.get("yt_total_comments", 0).fillna(0)
    views = df.get("yt_total_views", 0).fillna(0)
    return (likes + comments) / (views + 1)


def compute_trend_score(df: pd.DataFrame, features: List[str] = None) -> pd.Series:
    # Default features used to compute a composite trend score
    if features is None:
        features = [
            "trends_slope",
            "trends_mean",
            "trends_std",
            "yt_total_views",
            "yt_total_likes",
            "yt_total_comments",
            "ali_avg_sale_price",
            "ali_avg_evaluate_rate",
        ]

    # Ensure columns exist and fillna
    df_local = df.copy()
    for c in features:
        if c not in df_local.columns:
            df_local[c] = 0
        df_local[c] = pd.to_numeric(df_local[c], errors="coerce").fillna(0)

    # Add engagement_rate derived field
    df_local["engagement_rate"] = compute_engagement_rate(df_local)
    # Use MinMax scaler per feature to 0..1
    scaler = MinMaxScaler()
    scale_cols = [c for c in features if c in df_local.columns] + ["engagement_rate"]
    X = df_local[scale_cols].values.astype(float)
    X_scaled = scaler.fit_transform(X)

    # Weights chosen to reflect 'MUY IMPORTANTES' in user's spec
    # trends_slope, yt_total_views, engagement_rate get higher weight
    w = np.ones(X_scaled.shape[1])
    col_to_idx = {col: i for i, col in enumerate(scale_cols)}
    if "trends_slope" in col_to_idx:
        w[col_to_idx["trends_slope"]] = 3.0
    if "yt_total_views" in col_to_idx:
        w[col_to_idx["yt_total_views"]] = 3.0
    if "engagement_rate" in col_to_idx:
        w[col_to_idx["engagement_rate"]] = 3.0
    if "trends_mean" in col_to_idx:
        w[col_to_idx["trends_mean"]] = 1.5
    if "trends_std" in col_to_idx:
        w[col_to_idx["trends_std"]] = 1.5
    if "ali_avg_sale_price" in col_to_idx:
        w[col_to_idx["ali_avg_sale_price"]] = 1.2
    if "ali_avg_evaluate_rate" in col_to_idx:
        w[col_to_idx["ali_avg_evaluate_rate"]] = 1.0

    raw_score = (X_scaled * w).sum(axis=1)
    # Normalize to 0-100
    score_min, score_max = raw_score.min(), raw_score.max()
    if score_max - score_min <= 0:
        trend_score = np.zeros_like(raw_score)
    else:
        trend_score = 100 * (raw_score - score_min) / (score_max - score_min)

    return pd.Series(trend_score, index=df.index)


def create_future_target(df: pd.DataFrame, method: str = "percentile", field: str = "yt_total_views", percentile: int = 75, threshold: float = None) -> pd.Series:
    """
    Create a proxy future target `future_success`.

    method: 'percentile' -> use percentile on `field` to mark top-X% as success
            'threshold'  -> use provided threshold value on `field`
    """
    if field not in df.columns:
        raise ValueError(f"Field {field} not in dataframe")
    vals = pd.to_numeric(df[field], errors="coerce").fillna(0)
    if method == "percentile":
        pct = np.percentile(vals, percentile)
        print(f"Creating future_success using {field} > {percentile}th percentile = {pct}")
        return (vals > pct).astype(int)
    elif method == "threshold":
        if threshold is None:
            raise ValueError("threshold must be provided when method='threshold'")
        print(f"Creating future_success using {field} > {threshold}")
        return (vals > threshold).astype(int)
    else:
        raise ValueError("unknown method")


def advanced_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Parse generated_at
    if "generated_at" in df.columns:
        df["generated_at"] = pd.to_datetime(df["generated_at"], errors="coerce")
        df["month"] = df["generated_at"].dt.month
        df["quarter"] = df["generated_at"].dt.quarter
        df["day_of_week"] = df["generated_at"].dt.dayofweek
        # pandas >=1.1 returns IsoCalendar as DataFrame
        try:
            df["week_of_year"] = df["generated_at"].dt.isocalendar().week
        except Exception:
            df["week_of_year"] = df["generated_at"].dt.week
    else:
        # If not present, it's ok; featureers will continue
        pass

    # Momentum features
    for c in ["trends_last_value", "trends_first_value", "trends_count"]:
        if c not in df.columns:
            df[c] = 0

    df["trend_growth"] = pd.to_numeric(df["trends_last_value"], errors="coerce").fillna(0) - pd.to_numeric(df["trends_first_value"], errors="coerce").fillna(0)
    df["trend_acceleration"] = df["trend_growth"] / (pd.to_numeric(df["trends_count"], errors="coerce").fillna(0) + 1)

    # Stability
    df["trends_mean"] = pd.to_numeric(df.get("trends_mean", 0), errors="coerce").fillna(0)
    df["trends_std"] = pd.to_numeric(df.get("trends_std", 0), errors="coerce").fillna(0)
    df["stability_score"] = df["trends_mean"] / (df["trends_std"] + 1)

    # YouTube advanced
    for c in ["yt_total_views", "yt_videos_count", "yt_total_likes", "yt_total_comments", "trends_slope"]:
        if c not in df.columns:
            df[c] = 0

    # social_velocity: average engagement (likes+comments) per video
    likes = pd.to_numeric(df.get("yt_total_likes", 0), errors="coerce").fillna(0)
    comments = pd.to_numeric(df.get("yt_total_comments", 0), errors="coerce").fillna(0)
    videos = pd.to_numeric(df.get("yt_videos_count", 0), errors="coerce").fillna(0)

    df["social_velocity"] = (likes + comments) / (videos + 1)

    # Reduce direct dependence on views by adding comment/like ratios
    # comment_ratio: comments relative to likes (higher -> more intent)
    df["comment_ratio"] = comments / (likes + 1)
    # interaction_balance: balance of interactions relative to total engagement
    df["interaction_balance"] = (comments + 1) / (likes + comments + 1)

    # trend_quality: slope * stability (detects consistent growing trends)
    df["trend_quality"] = pd.to_numeric(df.get("trends_slope", 0), errors="coerce").fillna(0) * pd.to_numeric(df.get("stability_score", 0), errors="coerce").fillna(0)

    # AliExpress features
    for c in ["ali_avg_sale_price", "ali_avg_evaluate_rate"]:
        if c not in df.columns:
            df[c] = 0
    df["price_score"] = 1.0 / (pd.to_numeric(df["ali_avg_sale_price"], errors="coerce").fillna(0) + 1)
    df["value_score"] = pd.to_numeric(df["ali_avg_evaluate_rate"], errors="coerce").fillna(0) / (pd.to_numeric(df["ali_avg_sale_price"], errors="coerce").fillna(0) + 1)

    # New trend-based features
    # volatility: normalized variation relative to mean
    df["volatility"] = pd.to_numeric(df.get("trends_std", 0), errors="coerce").fillna(0) / (
        pd.to_numeric(df.get("trends_mean", 0), errors="coerce").fillna(0) + 1
    )

    # momentum_strength: slope * count (captures cumulative momentum)
    df["momentum_strength"] = pd.to_numeric(df.get("trends_slope", 0), errors="coerce").fillna(0) * pd.to_numeric(df.get("trends_count", 0), errors="coerce").fillna(0)

    # consistency_score: smoother normalization to avoid domination
    df["consistency_score"] = np.exp(-pd.to_numeric(df.get("trends_std", 0), errors="coerce").fillna(0))

    # engagement_quality: comments per like (more comments -> higher quality)
    df["engagement_quality"] = pd.to_numeric(df.get("yt_total_comments", 0), errors="coerce").fillna(0) / (
        pd.to_numeric(df.get("yt_total_likes", 0), errors="coerce").fillna(0) + 1
    )

    # Time-series derived features (if raw series available)
    # Expecting an optional column `trends_series` containing a list-like sequence per row
    def compute_series_features(row):
        try:
            series = row.get("trends_series", None)
            if series is None:
                return pd.Series({
                    "rolling_slope_7d": 0.0,
                    "rolling_slope_30d": 0.0,
                    "days_trending": 0,
                    "acceleration_change": 0.0,
                })

            # try to coerce to list of floats
            if isinstance(series, str):
                import json
                try:
                    series = json.loads(series)
                except Exception:
                    # fallback to eval-ish (if saved as python list string)
                    series = eval(series)
            series = np.array([float(x) for x in series])
            n = len(series)
            def slope_of_window(arr):
                if len(arr) < 2:
                    return 0.0
                x = np.arange(len(arr))
                m = np.polyfit(x, arr, 1)[0]
                return float(m)

            # rolling slopes: last window
            rolling_slope_7d = slope_of_window(series[-7:]) if n >= 1 else 0.0
            rolling_slope_30d = slope_of_window(series[-30:]) if n >= 1 else 0.0

            # days_trending: consecutive days of non-decreasing values at the end
            days = 0
            for i in range(n - 1, 0, -1):
                if series[i] >= series[i - 1]:
                    days += 1
                else:
                    break

            # acceleration: difference between recent slopes (last 2 windows of size 7)
            if n >= 14:
                prev_slope = slope_of_window(series[-14:-7])
                curr_slope = slope_of_window(series[-7:])
                acceleration_change = curr_slope - prev_slope
            else:
                acceleration_change = 0.0

            return pd.Series({
                "rolling_slope_7d": rolling_slope_7d,
                "rolling_slope_30d": rolling_slope_30d,
                "days_trending": int(days),
                "acceleration_change": float(acceleration_change),
            })
        except Exception:
            return pd.Series({
                "rolling_slope_7d": 0.0,
                "rolling_slope_30d": 0.0,
                "days_trending": 0,
                "acceleration_change": 0.0,
            })

    # apply series features row-wise (fast enough for moderate datasets)
    if "trends_series" in df.columns:
        series_feats = df.apply(compute_series_features, axis=1)
        df = pd.concat([df, series_feats], axis=1)
    else:
        # create defaults to keep pipeline stable
        df["rolling_slope_7d"] = 0.0
        df["rolling_slope_30d"] = 0.0
        df["days_trending"] = 0
        df["acceleration_change"] = 0.0

    return df


def prepare_features(df: pd.DataFrame, feature_cols: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    df_local = df.copy()
    # Categorical encoding
    cat_cols = [c for c in ["country", "region", "language", "category_name"] if c in df_local.columns]
    if len(cat_cols) > 0:
        df_local = pd.get_dummies(df_local, columns=cat_cols, drop_first=False)

    # Ensure feature cols exist
    available = []
    for c in feature_cols:
        if c in df_local.columns:
            available.append(c)
    # Add any dummy columns that start with the categorical names
    dummy_cols = [c for c in df_local.columns if any(c.startswith(prefix + "_") for prefix in cat_cols)]
    final_cols = available + dummy_cols
    X = df_local[final_cols].fillna(0)
    X = X.astype(float)

    return X, final_cols


def make_multiclass_target(trend_score: pd.Series, thresholds=(80, 50)) -> pd.Series:
    # Deprecated: replaced by percentile-based target. Keep for compatibility.
    t_high, t_medium = thresholds
    def cat(v):
        if v >= t_high:
            return "HIGH"
        elif v >= t_medium:
            return "MEDIUM"
        else:
            return "LOW"

    return trend_score.apply(cat)


def make_multiclass_target_percentile(trend_score: pd.Series, high_pct: float = 0.90, med_pct: float = 0.70) -> pd.Series:
    """
    Create multiclass labels from trend_score using percentiles.
    HIGH: > high_pct (e.g. top 10%)
    MEDIUM: between med_pct and high_pct (e.g. 70-90)
    LOW: rest
    """
    vals = pd.to_numeric(trend_score, errors="coerce").fillna(0)
    high_thr = np.percentile(vals, high_pct * 100)
    med_thr = np.percentile(vals, med_pct * 100)
    def cat(v):
        if v > high_thr:
            return "HIGH"
        elif v > med_thr:
            return "MEDIUM"
        else:
            return "LOW"

    print(f"Creating multiclass target: HIGH > {high_pct*100}th pct = {high_thr}, MEDIUM > {med_pct*100}th pct = {med_thr}")
    return vals.apply(cat)


def train_classifier(df: pd.DataFrame, feature_cols: List[str], target_col: str, model_path: str):
    if XGBClassifier is None:
        print("xgboost not installed; skipping classifier training")
        return None

    # Prepare X and y with categorical encoding
    X_df, final_cols = prepare_features(df, feature_cols)
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y = le.fit_transform(df[target_col].astype(str).values)

    # Decide multiclass vs binary
    classes = np.unique(y)
    n_classes = len(classes)

    scale_pos_weight = 1
    if n_classes == 2:
        neg = int((y == 0).sum())
        pos = int((y == 1).sum())
        if pos > 0 and neg / pos > 1.5:
            scale_pos_weight = float(neg) / float(pos)

    # Configure classifier depending on number of classes
    if n_classes > 2:
        clf = XGBClassifier(
            objective="multi:softprob",
            num_class=n_classes,
            max_depth=3,
            learning_rate=0.03,
            n_estimators=300,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1,
            reg_lambda=2,
            min_child_weight=3,
            gamma=0.1,
            early_stopping_rounds=20,
            random_state=42,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
    else:
        # binary
        clf = XGBClassifier(
            objective="binary:logistic",
            max_depth=3,
            learning_rate=0.03,
            n_estimators=300,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1,
            reg_lambda=2,
            min_child_weight=3,
            gamma=0.1,
            early_stopping_rounds=20,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            use_label_encoder=False,
            eval_metric="logloss",
        )

    # Cross-validation
    n_splits = 5 if len(df) >= 50 else 3
    # Ajustar n_splits si alguna clase tiene menos muestras que n_splits
    try:
        class_counts = np.bincount(y)
        min_class_count = int(class_counts.min()) if class_counts.size > 0 else 0
    except Exception:
        min_class_count = 0
    if min_class_count < n_splits:
        new_n = max(2, min_class_count)
        print(f"Adjusting n_splits from {n_splits} to {new_n} because least populated class has {min_class_count} samples.")
        n_splits = new_n
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    f1s, precs, recs, rocs = [], [], [], []
    X_vals = X_df.values
    for train_idx, test_idx in skf.split(X_vals, y):
        X_tr, X_te = X_vals[train_idx], X_vals[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        try:
            # fit without passing early_stopping_rounds (set in constructor)
            clf.fit(
                X_tr,
                y_tr,
                eval_set=[(X_te, y_te)],
                verbose=False,
            )
        except Exception as e:
            print("Skipping fold due to training error:", e)
            continue
        preds = clf.predict(X_te)
        probs = clf.predict_proba(X_te) if hasattr(clf, "predict_proba") else None
        f1s.append(f1_score(y_te, preds, average="macro"))
        precs.append(precision_score(y_te, preds, average="macro", zero_division=0))
        recs.append(recall_score(y_te, preds, average="macro", zero_division=0))
        # ROC-AUC is only computed for binary
        if n_classes == 2 and probs is not None and probs.shape[1] == 2:
            rocs.append(roc_auc_score(y_te, probs[:, 1]))

    print(f"CV f1 (mean,std): {np.mean(f1s):.4f} ± {np.std(f1s):.4f}")
    print(f"CV precision (mean,std): {np.mean(precs):.4f} ± {np.std(precs):.4f}")
    print(f"CV recall (mean,std): {np.mean(recs):.4f} ± {np.std(recs):.4f}")
    if len(rocs) > 0:
        print(f"CV ROC-AUC (mean,std): {np.mean(rocs):.4f} ± {np.std(rocs):.4f}")

    # Retrain on full data with a validation split for early stopping
    try:
        X_train_full, X_val_full, y_train_full, y_val_full = train_test_split(
            X_vals, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y))>1 else None
        )
        clf.fit(
            X_train_full,
            y_train_full,
            eval_set=[(X_val_full, y_val_full)],
            verbose=False,
        )
    except Exception:
        clf.fit(X_vals, y)

    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    joblib.dump({"model": clf, "features": final_cols, "label_encoder": le}, model_path)
    print(f"Saved classifier to {model_path}")

    # Feature importance
    try:
        importance = clf.feature_importances_
        print("Feature importances:")
        for f, i in zip(final_cols, importance):
            print(f, float(i))
    except Exception:
        pass

    # SHAP explainability (optional)
    try:
        explain_model_shap(clf, X_df, "shap_importance.csv")
    except Exception:
        pass

    # Save success probabilities and top products
    try:
        probs = clf.predict_proba(X_df)[:, 1]
        # align with original df index
        df_index = getattr(X_df, 'index', None)
        if df_index is not None:
            # create a predictions DataFrame attached to original df via index
            preds_df = pd.DataFrame(index=df_index)
            # Handle multiclass: determine probability of HIGH class if present
            probs_all = clf.predict_proba(X_df)
            success_prob = None
            try:
                classes_labels = list(le.classes_)
                if "HIGH" in classes_labels:
                    high_idx = classes_labels.index("HIGH")
                    success_prob = probs_all[:, high_idx]
                elif n_classes == 2:
                    # binary fallback: use positive class
                    success_prob = probs_all[:, 1]
                else:
                    # fallback: use probability of top predicted class
                    success_prob = np.max(probs_all, axis=1)
            except Exception:
                # safest fallback
                success_prob = np.max(probs_all, axis=1)

            preds_df["success_probability"] = success_prob
            preds_df["high_potential"] = (preds_df["success_probability"] > 0.7).astype(int)
            # Merge predictions back into the original dataframe if available
            try:
                # df is in outer scope for this function call; attempt to set columns
                # If df is not accessible, just save preds_df
                df["success_probability"] = preds_df["success_probability"].values
                df["high_potential"] = preds_df["high_potential"].values
                # Normalize trend_score and social_velocity for final scoring
                try:
                    from sklearn.preprocessing import MinMaxScaler
                    scaler = MinMaxScaler()
                    norm_trend = scaler.fit_transform(df[["trend_score"]].fillna(0).values.reshape(-1, 1)).ravel()
                    norm_trend_quality = scaler.fit_transform(df[["trend_quality"]].fillna(0).values.reshape(-1, 1)).ravel() if "trend_quality" in df.columns else np.zeros(len(df))
                    norm_consistency = scaler.fit_transform(df[["consistency_score"]].fillna(0).values.reshape(-1, 1)).ravel() if "consistency_score" in df.columns else np.zeros(len(df))
                    norm_social = scaler.fit_transform(df[["social_velocity"]].fillna(0).values.reshape(-1, 1)).ravel() if "social_velocity" in df.columns else np.zeros(len(df))
                except Exception:
                    norm_trend = np.nan_to_num(df.get("trend_score", 0).values)
                    norm_trend_quality = np.nan_to_num(df.get("trend_quality", 0).values)
                    norm_consistency = np.nan_to_num(df.get("consistency_score", 0).values)
                    norm_social = np.nan_to_num(df.get("social_velocity", 0).values)

                df["success_probability"] = preds_df["success_probability"].values
                df["high_potential"] = preds_df["high_potential"].values

                # final_score: weighted combination
                # Product Opportunity Score (commercial): weights specified by product owner
                # success_probability 40%, trend_quality 30%, consistency_score 15%, social_velocity 15%
                df["product_opportunity_score"] = (
                    df["success_probability"] * 0.4
                    + norm_trend_quality * 0.3
                    + norm_consistency * 0.15
                    + norm_social * 0.15
                )

                # map into tiers for quick interpretation
                def tier_from_score(s):
                    if s >= 0.8:
                        return "HIGH"
                    elif s >= 0.55:
                        return "MEDIUM"
                    else:
                        return "LOW"

                df["opportunity_tier"] = df["product_opportunity_score"].apply(tier_from_score)
                df.to_csv("dataset_predictions.csv", index=False)
                top_products = df.sort_values("product_opportunity_score", ascending=False)
                top_products.to_csv("top_products.csv", index=False)
                print("Wrote dataset_predictions.csv and top_products.csv")
            except Exception:
                preds_df.to_csv("dataset_predictions.csv")
                preds_df.sort_values("success_probability", ascending=False).to_csv("top_products.csv")
    except Exception as e:
        print("Could not save success probabilities:", e)

    return clf


def train_regressor(df: pd.DataFrame, feature_cols: List[str], target_col: str, model_path: str):
    if XGBRegressor is None:
        print("xgboost not installed; skipping regressor training")
        return None

    X_df, final_cols = prepare_features(df, feature_cols)
    X = X_df.values
    y = df[target_col].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    reg = XGBRegressor(
        max_depth=3,
        learning_rate=0.03,
        n_estimators=200,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1,
        reg_lambda=2,
        random_state=42,
    )
    reg.fit(X_train, y_train)
    preds = reg.predict(X_test)
    print("Regressor RMSE:", np.sqrt(mean_squared_error(y_test, preds)))
    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    joblib.dump({"model": reg, "features": final_cols}, model_path)
    print(f"Saved regressor to {model_path}")
    return reg


def train_ranker(df: pd.DataFrame, feature_cols: List[str], relevance_col: str, groupby_col: str, model_path: str):
    if XGBRanker is None:
        print("xgboost not installed; skipping ranker training")
        return None

    # We'll rank items within each group defined by groupby_col using relevance_col
    df_local = df.dropna(subset=[groupby_col]).copy()
    groups = []
    X_list = []
    y_list = []
    for g, gdf in df_local.groupby(groupby_col):
        if len(gdf) < 2:
            continue
        groups.append(len(gdf))
        X_list.append(gdf[feature_cols].fillna(0).values)
        y_list.append(gdf[relevance_col].values)

    if len(groups) == 0:
        print("Not enough groups for ranking")
        return None

    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    ranker = XGBRanker(objective="rank:pairwise", learning_rate=0.1, n_estimators=100, random_state=42)
    ranker.fit(X, y, group=groups)
    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    joblib.dump(ranker, model_path)
    print(f"Saved ranker to {model_path}")

    # Produce a ranked_products.csv with rank per category using the trained ranker
    try:
        # reconstruct per-group predictions to compute ranks
        all_ranks = []
        start = 0
        df_local = df.dropna(subset=[groupby_col]).copy()
        for g, gdf in df_local.groupby(groupby_col):
            gX = gdf[feature_cols].fillna(0).values
            if gX.shape[0] == 0:
                continue
            preds = ranker.predict(gX)
            # lower value = better or higher? XGBRanker outputs scores; higher -> better
            order = np.argsort(-preds)
            ranks = np.empty_like(order)
            ranks[order] = np.arange(1, len(preds) + 1)
            temp = gdf.copy()
            temp["rank_score"] = preds
            temp["rank_in_category"] = ranks
            all_ranks.append(temp)

        if len(all_ranks) > 0:
            ranked = pd.concat(all_ranks, axis=0)
            # choose identifier column if present
            id_col = None
            for c in ["product_id", "sku", "title"]:
                if c in ranked.columns:
                    id_col = c
                    break
            if id_col is None:
                ranked = ranked.reset_index().rename(columns={"index": "row_index"})
                id_col = "row_index"

            out_cols = [id_col, groupby_col, "rank_score", "rank_in_category", "product_opportunity_score"]
            existing = [c for c in out_cols if c in ranked.columns]
            ranked[existing].sort_values([groupby_col, "rank_in_category"]).to_csv("ranked_products.csv", index=False)
            print("Wrote ranked_products.csv")
    except Exception as e:
        print("Could not write ranked_products.csv:", e)

    return ranker


def explain_model_shap(model, X: pd.DataFrame, out_path: str = "shap_importance.csv") -> Optional[pd.DataFrame]:
    try:
        # defer import so code runs even if shap is not installed; we catch ImportError
        import shap  # type: ignore
    except Exception:
        print("shap not installed; skipping SHAP explainability")
        return None

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        # shap_values can be list (multiclass) or array. Compute mean(|shap|) per feature
        if isinstance(shap_values, list):
            abs_mean = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
        elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
            # shape: (n_samples, n_classes, n_features) -> average over samples and classes
            abs_mean = np.mean(np.abs(shap_values), axis=(0, 1))
        else:
            abs_mean = np.abs(shap_values).mean(axis=0)

        abs_mean = np.array(abs_mean).flatten()
        # ensure same length between columns and importance
        min_len = min(len(X.columns), len(abs_mean))
        importance = pd.DataFrame({
            "feature": list(X.columns)[:min_len],
            "mean_abs_shap": abs_mean[:min_len],
        })
        importance = importance.sort_values("mean_abs_shap", ascending=False)
        importance.to_csv(out_path, index=False)
        print(f"Wrote SHAP feature importance to {out_path}")
        return importance
    except Exception as e:
        print("SHAP explanation failed:", e)
        return None


def compute_category_score(df: pd.DataFrame) -> pd.DataFrame:
    # Aggregate by category_name and compute composite score as recommended
    grp = df.groupby("category_name")
    agg = grp.agg(
        trend_quality=("trend_quality", "mean"),
        consistency_score=("consistency_score", "mean"),
        momentum_strength=("momentum_strength", "mean"),
        engagement_quality=("engagement_quality", "mean"),
        evaluate_rate=("ali_avg_evaluate_rate", "mean"),
    ).fillna(0)

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(
        agg[
            [
                "trend_quality",
                "consistency_score",
                "momentum_strength",
                "engagement_quality",
            ]
        ].values
    )

    agg["normalized_trend_quality"] = scaled[:, 0]
    agg["normalized_consistency"] = scaled[:, 1]
    agg["normalized_momentum"] = scaled[:, 2]
    agg["normalized_engagement"] = scaled[:, 3]

    agg["category_score"] = (
        0.35 * agg["normalized_trend_quality"]
        + 0.30 * agg["normalized_consistency"]
        + 0.20 * agg["normalized_momentum"]
        + 0.15 * agg["normalized_engagement"]
    )
    # Scale to 0-100
    agg["category_score"] = 100 * (agg["category_score"] - agg["category_score"].min()) / (
        agg["category_score"].max() - agg["category_score"].min() + 1e-9
    )
    return agg.sort_values("category_score", ascending=False)


def create_real_target_from_sales(df: pd.DataFrame, pct: float = 0.80) -> Optional[str]:
    """
    If the dataframe contains a sales/revenue/orders-like column, create
    `future_success_sales` (binary) and `future_potential` (multiclass by percentile)
    and return the field used. If no suitable field found, return None.
    """
    candidates = [
        "future_sales",
        "sales",
        "future_revenue",
        "revenue",
        "future_profit",
        "profit",
        "future_orders",
        "orders",
    ]
    for c in candidates:
        if c in df.columns:
            vals = pd.to_numeric(df[c], errors="coerce").fillna(0)
            thr = np.percentile(vals, pct * 100)
            df["future_success_sales"] = (vals > thr).astype(int)
            # create multiclass based on percentiles of the sales-like metric
            high_thr = np.percentile(vals, 0.90 * 100)
            med_thr = np.percentile(vals, 0.70 * 100)
            def cat(v):
                if v > high_thr:
                    return "HIGH"
                elif v > med_thr:
                    return "MEDIUM"
                else:
                    return "LOW"
            df["future_potential"] = vals.apply(cat)
            print(f"Created sales-based target from '{c}' using {pct*100}% threshold={thr}")
            return c
    return None


def main(args):
    df = load_data(args.input)
    print("Loaded rows:", len(df))
    # Feature engineering: add momentum, stability, ratios, temporal features
    df = advanced_feature_engineering(df)

    # Correlaciones rápidas con yt_total_views para detectar leakage
    try:
        corr = df.corr(numeric_only=True)
        print("Top correlations with yt_total_views:")
        print(corr["yt_total_views"].sort_values(ascending=False).head(20))
    except Exception as e:
        print("Could not compute correlations:", e)

    # Compute trend score (kept for analysis but NOT used as classifier target)
    df["trend_score"] = compute_trend_score(df)
    # engagement_rate may be recomputed/overwritten by advanced features
    df["engagement_rate"] = compute_engagement_rate(df)
    df.to_csv("dataset_with_trend_score.csv", index=False)
    print("Wrote dataset_with_trend_score.csv")

    # Prepare features list
    # Remove features that leak the target (views-based features)
    # Minimal, robust feature set to avoid leakage and use true trend signals
    feature_cols = [
        "trend_quality",
        "volatility",
        "momentum_strength",
        "consistency_score",
    ]

    # Prefer real sales-like target if available; otherwise fallback to trend_score proxy
    used_sales_field = create_real_target_from_sales(df, pct=0.80)
    if used_sales_field is not None:
        print(f"Using real sales-based target from '{used_sales_field}'")
        print(df["future_potential"].value_counts())
    else:
        print("No sales/revenue/orders field found — using trend_score as proxy (document in TFM).")
        df["future_potential"] = make_multiclass_target_percentile(df.get("trend_score", 0), high_pct=0.90, med_pct=0.70)
        print("future_potential distribution (proxy):")
        print(df["future_potential"].value_counts())

    # FASE 2: classification (binary)
    if args.do_classifier:
        train_classifier(df, feature_cols, "future_potential", "models/xgb_classifier.joblib")

    # FASE 3: ranking products within category
    if args.do_ranker:
        # Ensure we have product_opportunity_score (produced by classifier)
        if "product_opportunity_score" not in df.columns:
            print("product_opportunity_score not found; running classifier to generate it...")
            train_classifier(df, feature_cols, "future_potential", "models/xgb_classifier.joblib")
        # train ranker using product_opportunity_score as relevance, grouped by category_name
        if "category_name" not in df.columns:
            print("category_name column missing; cannot train ranker")
        else:
            print("Training XGBRanker by category_name using product_opportunity_score as relevance...")
            train_ranker(df, feature_cols, "product_opportunity_score", "category_name", "models/xgb_ranker.joblib")

    # FASE 4: predictive scoring
    if args.do_regressor:
        print("Skipping regressor training (--do-regressor) due to leakage from trend_score. Re-enable when ready.")

    # FASE 4b: category ranking
    if args.do_category_score:
        cat_scores = compute_category_score(df)
        cat_scores.to_csv("category_scores.csv")
        print("Wrote category_scores.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_DATA)
    parser.add_argument("--do-classifier", dest="do_classifier", action="store_true")
    parser.add_argument("--do-ranker", dest="do_ranker", action="store_true")
    parser.add_argument("--do-regressor", dest="do_regressor", action="store_true")
    parser.add_argument("--do-category-score", dest="do_category_score", action="store_true")
    args = parser.parse_args()
    main(args)
