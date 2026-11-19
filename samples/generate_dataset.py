from __future__ import annotations
import csv, json, random
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SEED=20261119
random.seed(SEED)
cities=[('Bengaluru','560001'),('Bangalore','560002'),('Delhi','110001'),('Mumbai','400001'),('Pune','411001'),('Chennai','600001'),('Kolkata','700001'),('Hyderabad','500001')]
categories=['Books','Electronics','Home','Sports']
statuses=['shipped','processing','delivered','cancelled']
start=date(2025,1,1)
truth=[]
for i in range(1,1001):
    city,pin=cities[(i-1)%len(cities)]
    qty=random.randint(1,5); price=round(random.uniform(8,250),2)
    d=start+timedelta(days=random.randrange(300))
    ship=d+timedelta(days=random.randint(1,8))
    if i==61:
        ship=d+timedelta(days=20)
        while ship.day<=12: ship+=timedelta(days=1)
    truth.append({
      'order_id':f'O{i:05d}','customer_id':f'C{((i-1)//2)+1:04d}',
      'customer_name':f'Synthetic Customer {((i-1)//2)+1:04d}',
      'email':f'customer{((i-1)//2)+1:04d}@example.test','phone':f'555010{i%1000:03d}',
      'city':city,'pincode':pin,'order_date':d.isoformat(),'ship_date':ship.isoformat(),
      'category':categories[(i-1)%len(categories)],'quantity':str(40 if i==131 else qty),'unit_price':f'{price:.2f}',
      'total':f'{(40 if i==131 else qty)*price:.2f}','status':statuses[(i-1)%len(statuses)]
    })

def write_csv(path, rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(truth[0]));w.writeheader();w.writerows(rows)
write_csv(ROOT/'orders_clean_truth.csv',truth)
dirty=[row.copy() for row in truth]
errors=[]
def inject(error_id,index,column,value,category,outcome,detail):
    row=dirty[index]; old=row[column]; row[column]=value
    errors.append({'error_id':error_id,'row_id':f'row_{index+1}','source_row_id':f'row_{index+1}','column':column,'original_value':old,'injected_value':value,'category':category,'expected_outcome':outcome,'detail':detail})
# Chosen indices avoid clobbering unrelated examples.
inject('missing-customer-name',10,'customer_name','', 'missing','flag_or_abstain','Blank value has no safe inferred replacement.')
inject('placeholder-email',20,'email','N/A','missing','needs_approval_or_flag','Configured placeholder is detected; substitution to null is not imputed.')
inject('placeholder-phone',30,'phone','-','missing','needs_approval_or_flag','Configured placeholder token.')
inject('invalid-email',40,'email','not-an-email','invalid_format','flag_only','Conservative syntax detector; no guessed replacement.')
inject('invalid-quantity',50,'quantity','several','invalid_format','flag_only','Mostly numeric quantity column contains text.')
inject('mixed-date-format',60,'ship_date',date.fromisoformat(truth[60]['ship_date']).strftime('%d/%m/%Y'),'invalid_format','auto_apply_if_simulation_passes','Unambiguous day-first representation of the clean truth date (day exceeds 12).')
inject('ambiguous-order-date',70,'order_date','03/04/2025','invalid_format','refuse_or_flag','Date may mean March 4 or April 3; locale is unknown.')
inject('city-case-whitespace',80,'city',' bengaluru ','inconsistent','needs_approval','Equivalent normalized category spelling.')
inject('category-case',88,'category','books','inconsistent','needs_approval','Case-only category variant in a clean-truth Books row.')
inject('near-distinct-city',100,'city','Bangaluru','inconsistent','flag_only','Similar-looking value is kept distinct without evidence of equivalence.')
inject('arithmetic-inconsistency',110,'total','99999.99','relationship','flag_only','Quantity, price and total conflict; wrong source field is unknown.')
inject('date-order-inconsistency',120,'ship_date','2024-12-31','relationship','flag_only','Ship date precedes order date; no correction is safe.')
inject('unrecoverable-missing-price',140,'unit_price','','missing','refuse_or_flag','No same-row or reliable functional-dependency evidence supports imputation.')
# Exact duplicate of an otherwise untouched clean row.
duplicate_source=250
dirty.append(dirty[duplicate_source].copy())
errors.append({'error_id':'exact-duplicate-row','row_id':f'row_{len(dirty)}','source_row_id':f'row_{duplicate_source+1}','column':None,'original_value':None,'injected_value':'duplicate of complete row','category':'duplicate','expected_outcome':'needs_approval','detail':'Exact complete-row duplicate is destructive and requires approval.'})
write_csv(ROOT/'orders_dirty.csv',dirty)
preservation=[{'row_id':'row_101','column':'city','value':truth[100]['city'],'category':'inconsistent','expected':'Similar-looking distinct spelling remains unmapped.'}]
injected={(e['row_id'],e['column']) for e in errors if e['column']}
def quantile(sorted_values,q):
    at=(len(sorted_values)-1)*q; lo=int(at); hi=min(len(sorted_values)-1,lo+1)
    return sorted_values[lo]+(sorted_values[hi]-sorted_values[lo])*(at-lo)
for column in ('quantity','unit_price','total'):
    values=[]
    for row in dirty[:-1]:
        try: values.append(float(row[column]))
        except ValueError: pass
    values.sort()
    if len(values)<8 or len(set(values))<4: continue
    q1,q3=quantile(values,.25),quantile(values,.75); iqr=q3-q1
    for index,row in enumerate(dirty[:-1]):
        try: value=float(row[column])
        except ValueError: continue
        if (value<q1-1.5*iqr or value>q3+1.5*iqr) and (f'row_{index+1}',column) not in injected and row[column]==truth[index][column]:
            preservation.append({'row_id':f'row_{index+1}','column':column,'value':row[column],'category':'anomaly','expected':'IQR outlier is a correct clean-truth value and must be preserved.'})
preservation.append({'row_id':'row_131','column':'quantity','value':truth[130]['quantity'],'category':'anomaly','expected':'IQR outlier is flagged and preserved; total is consistent.'})
(ROOT/'orders_error_manifest.json').write_text(json.dumps({'dataset':'DataFix synthetic e-commerce orders','seed':SEED,'tuning_seed':7319,'clean_rows':len(truth),'dirty_rows':len(dirty),'columns':list(truth[0]),'synthetic_personal_data':True,'errors':errors,'preservation_cases':preservation},indent=2)+'\n',encoding='utf-8')
print(f'generated clean={len(truth)} dirty={len(dirty)} columns={len(truth[0])} errors={len(errors)}')
