"""Real PySpark batch pipeline with Parquet outputs and conflict detection."""
from pathlib import Path

def process(input_path, output):
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.types import StructType, StructField, StringType
    from generator.generate import FIELDS
    if not list(Path(input_path).glob('*.csv')): raise ValueError('No CSV input files found')
    spark=SparkSession.builder.appName('MultiStoreAnalytics').getOrCreate()
    spark.conf.set('spark.sql.ansi.enabled','false')
    try:
        schema=StructType([StructField(x,StringType(),True) for x in FIELDS])
        raw=spark.read.option('header',True).schema(schema).csv(str(Path(input_path)/'*.csv')).cache()
        df=raw.withColumn('parsed_date',F.to_date('sold_on','yyyy-MM-dd'))
        for name in ['quantity','unit_price_cents','discount_cents']:
            df=df.withColumn(name+'_n',F.col(name).cast('long'))
        valid=(F.col('sale_line_id').rlike(r'^LINE-\d+$') & F.col('store_id').rlike(r'^STORE-\d+$') & F.col('product_id').rlike(r'^PROD-\d+$') & F.col('region').isin('North','South','East','West') & F.col('category').isin('Electronics','Home','Sport','Fashion','Grocery') & F.col('parsed_date').isNotNull() & (F.date_format('parsed_date','yyyy-MM-dd')==F.col('sold_on')))
        for name in ['quantity','unit_price_cents','discount_cents']:
            valid=valid & F.col(name).rlike(r'^\d{1,9}$')
        valid=F.coalesce(valid & (F.col('quantity_n')>0) & (F.col('discount_cents_n')<=F.col('quantity_n')*F.col('unit_price_cents_n')),F.lit(False))
        accepted=df.where(valid).select(*[F.col(x+'_n').alias(x) if x in ['quantity','unit_price_cents','discount_cents'] else F.col(x) for x in FIELDS]).cache()
        rejected=df.where(~valid)
        rejected.withColumn('reason',F.lit('Schema or business validation failed')).write.mode('error').json(str(Path(output)/'rejected'))
        # Any non-identical valid records sharing an ID fail the batch explicitly.
        if accepted.dropDuplicates().groupBy('sale_line_id').count().where('count > 1').limit(1).count():
            raise ValueError('Conflicting duplicate sale_line_id found')
        clean=accepted.dropDuplicates(['sale_line_id']).cache()
        count=raw.count();bad=rejected.count();duplicates=accepted.count()-clean.count()
        clean=clean.withColumn('revenue_cents',F.col('quantity')*F.col('unit_price_cents')-F.col('discount_cents'))
        clean.write.mode('error').partitionBy('sold_on').parquet(str(Path(output)/'clean'))
        groups=clean.groupBy('sold_on','store_id','region','product_id','category').agg(F.sum('revenue_cents').alias('revenue_cents'),F.sum('quantity').alias('units'),F.count('*').alias('lines'))
        groups.write.mode('error').parquet(str(Path(output)/'aggregated'))
        # Only summaries travel to the publisher, never raw sales. Streaming iterator bounds driver memory.
        rows=(tuple(r) for r in groups.toLocalIterator())
        # Keep Spark alive until consumer has finished publication.
        return rows,count,bad,duplicates,spark
    except Exception:
        spark.stop();raise
