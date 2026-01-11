-- CreateEnum
CREATE TYPE "QueryStatus" AS ENUM ('RUNNING', 'DONE', 'ERROR');

-- CreateTable
CREATE TABLE "trend_queries" (
    "id" TEXT NOT NULL,
    "keyword" TEXT NOT NULL,
    "region" TEXT NOT NULL,
    "window_days" INTEGER NOT NULL,
    "baseline_days" INTEGER NOT NULL,
    "status" "QueryStatus" NOT NULL DEFAULT 'RUNNING',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(3),
    "error_message" TEXT,

    CONSTRAINT "trend_queries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trend_results" (
    "id" TEXT NOT NULL,
    "query_id" TEXT NOT NULL,
    "trend_score" DOUBLE PRECISION NOT NULL,
    "signals" JSONB NOT NULL,
    "explain" JSONB NOT NULL,
    "sources_used" TEXT[],
    "generated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "trend_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trend_series" (
    "id" BIGSERIAL NOT NULL,
    "query_id" TEXT NOT NULL,
    "date" DATE NOT NULL,
    "value" INTEGER NOT NULL,

    CONSTRAINT "trend_series_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trend_by_region" (
    "id" BIGSERIAL NOT NULL,
    "query_id" TEXT NOT NULL,
    "region" TEXT NOT NULL,
    "value" INTEGER NOT NULL,

    CONSTRAINT "trend_by_region_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_query_cache_lookup" ON "trend_queries"("keyword", "region", "window_days", "baseline_days");

-- CreateIndex
CREATE INDEX "idx_created_at" ON "trend_queries"("created_at");

-- CreateIndex
CREATE INDEX "idx_status" ON "trend_queries"("status");

-- CreateIndex
CREATE UNIQUE INDEX "trend_results_query_id_key" ON "trend_results"("query_id");

-- CreateIndex
CREATE INDEX "idx_result_query" ON "trend_results"("query_id");

-- CreateIndex
CREATE INDEX "idx_series_query" ON "trend_series"("query_id");

-- CreateIndex
CREATE INDEX "idx_series_date" ON "trend_series"("date");

-- CreateIndex
CREATE INDEX "idx_by_region_query" ON "trend_by_region"("query_id");

-- CreateIndex
CREATE INDEX "idx_by_region" ON "trend_by_region"("region");

-- AddForeignKey
ALTER TABLE "trend_results" ADD CONSTRAINT "trend_results_query_id_fkey" FOREIGN KEY ("query_id") REFERENCES "trend_queries"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trend_series" ADD CONSTRAINT "trend_series_query_id_fkey" FOREIGN KEY ("query_id") REFERENCES "trend_queries"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trend_by_region" ADD CONSTRAINT "trend_by_region_query_id_fkey" FOREIGN KEY ("query_id") REFERENCES "trend_queries"("id") ON DELETE CASCADE ON UPDATE CASCADE;
