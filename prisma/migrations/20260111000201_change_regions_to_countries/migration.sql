-- AlterTable: Rename column in trend_queries
ALTER TABLE "trend_queries" RENAME COLUMN "region" TO "country";

-- AlterIndex: Rename index in trend_queries (recreate with new column name)
DROP INDEX IF EXISTS "idx_query_cache_lookup";
CREATE INDEX "idx_query_cache_lookup" ON "trend_queries"("keyword", "country", "window_days", "baseline_days");

-- RenameTable: Rename trend_by_region to trend_by_country
ALTER TABLE "trend_by_region" RENAME TO "trend_by_country";

-- AlterTable: Rename column in trend_by_country
ALTER TABLE "trend_by_country" RENAME COLUMN "region" TO "country";

-- AlterIndex: Rename index in trend_by_country
ALTER INDEX "idx_by_region" RENAME TO "idx_by_country";
