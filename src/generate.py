"""Greedy CPU generation with the authors' 0-shot prompt (CodeEval-Pro eval/utils.py). python3 src/generate.py <humanevalpro|mbpppro> <model.gguf> <tag>"""
import sys, json, os, pandas as pd
from llama_cpp import Llama
b,mp,tag=sys.argv[1:4]
df=pd.read_parquet({'humanevalpro':'data/humaneval-pro.parquet','mbpppro':'data/mbpp-pro.parquet'}[b])
W="""You are an exceptionally intelligent coding assistant that consistently delivers accurate and reliable responses to user instructions.
@@ Instruction
{instruction}

@@ Response
{response}"""
llm=Llama(model_path=mp,n_ctx=4096,n_threads=4,verbose=False,seed=0)
out=f'results/gen_{b}_{tag}.jsonl'; done=set()
if os.path.exists(out): done={json.loads(l)['id'] for l in open(out)}
f=open(out,'a')
for r in df.itertuples():
    if int(r.id) in done: continue
    p1,p2=r.raw_problem.strip(),r.new_problem.strip()
    ins=f"Write a solution of python file to the following problems, the solution of the second problem requires single or multiple calls to the first solution.\n```python\n{p1}\n{p2}\n```"
    pre=f"```python\n{p1}\n"
    txt=llm(W.format(instruction=ins,response=pre),max_tokens=512,temperature=0,stop=["```\n","```\r","\n@@"])['choices'][0]['text']
    code=(p1+"\n"+txt).split("```")[0]
    f.write(json.dumps({'id':int(r.id),'code':code})+"\n"); f.flush()
