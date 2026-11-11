from datetime import date
import json
from app.storage import query

def filters(params):
    clauses=[];values=[]
    for key,column in [('start','day'),('end','day'),('region','region')]:
        value=params.get(key,'')
        if not value: continue
        if key in ('start','end'):
            date.fromisoformat(value)
            clauses.append(column+(' >= ?' if key=='start' else ' <= ?'))
        else:
            if value not in ['North','South','East','West']: raise ValueError('Unknown region')
            clauses.append('region = ?')
        values.append(value)
    if params.get('start') and params.get('end') and params['start']>params['end']: raise ValueError('Start date must precede end date')
    return (' WHERE '+' AND '.join(clauses) if clauses else ''),values

def response(path,params):
    if path=='/api/health': query('SELECT 1');return {'status':'ok'}
    if path=='/api/runs': return query('SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 50')
    if path=='/api/dataset':
        rows=query('SELECT metadata FROM dataset_meta WHERE singleton=1')
        return json.loads(rows[0]['metadata']) if rows else {}
    if path=='/api/filters': return {'regions':['North','South','East','West'],**query('SELECT MIN(day) AS start, MAX(day) AS end FROM daily_sales')[0]}
    where,args=filters(params)
    if path=='/api/overview':
        total=query('SELECT COALESCE(SUM(revenue_cents),0) AS revenue_cents, COALESCE(SUM(units),0) AS units, COALESCE(SUM(lines),0) AS sale_lines, COUNT(DISTINCT store_id) AS stores FROM daily_sales'+where,args)[0]
        meta=query('SELECT run_id,published_at FROM snapshot_meta WHERE singleton=1')
        return {**total,'snapshot':meta[0] if meta else None,'currency':'EUR'}
    specifications={
        '/api/trends':('day','day','day',''),
        '/api/stores':('store_id','store_id','revenue_cents DESC',' LIMIT 20'),
        '/api/products':('product_id','product_id','revenue_cents DESC',' LIMIT 20'),
        '/api/regions':('region','region','revenue_cents DESC',''),
        '/api/categories':('category','category','revenue_cents DESC',''),
    }
    if path not in specifications: raise KeyError(path)
    field,group,order,limit=specifications[path]
    return query(f'SELECT {field} AS label, SUM(revenue_cents) AS revenue_cents, SUM(units) AS units FROM daily_sales'+where+f' GROUP BY {group} ORDER BY {order}'+limit,args)
