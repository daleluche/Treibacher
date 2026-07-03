"""
run_all.py  -  Executa instâncias do Problema de Seleção de Processos
               GAMSPy + CPLEX | RESLIM = 10800 s (3 h) por instância

Uso:
    python run_all.py              # todos os 50 scripts
    python run_all.py Real         # apenas pasta Real
    python run_all.py 2X 3X        # apenas 2X e 3X
"""
import os, sys, subprocess, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDERS  = ["Real", "2X", "3X", "4X", "5X"]

def main():
    selected = sys.argv[1:] if len(sys.argv) > 1 else FOLDERS
    results  = []

    for folder in selected:
        folder_path = os.path.join(BASE_DIR, folder)
        if not os.path.isdir(folder_path):
            print(f"Pasta não encontrada: {folder_path}"); continue
        scripts = sorted(f for f in os.listdir(folder_path) if f.endswith(".py"))
        for script in scripts:
            script_path = os.path.join(folder_path, script)
            print(f"\n>>> {folder}/{script}")
            t0  = time.time()
            ret = subprocess.run([sys.executable, script_path])
            elapsed = time.time() - t0

            # Lê JSON de resultado (se existir)
            json_path = os.path.join(folder_path, "results",
                                     script.replace(".py", ".json"))
            obj, bound, gap, mstat, nodes = None, None, None, "?", None
            if os.path.exists(json_path):
                with open(json_path) as jf:
                    r = json.load(jf)
                obj   = r.get("objective_value")
                bound = r.get("best_bound")
                gap   = r.get("gap_pct")
                mstat = r.get("model_status", "?")
                nodes = r.get("num_nodes_used")

            results.append({
                "instance": f"{folder}/{script}",
                "time_s":   round(elapsed, 1),
                "obj":      obj,
                "bound":    bound,
                "gap_pct":  gap,
                "nodes":    nodes,
                "status":   mstat,
                "rc":       ret.returncode,
            })

    # Tabela resumo
    print("\n" + "="*90)
    print(f"{'Instância':<38} {'Tempo(s)':>8} {'Objetivo':>14} {'Bound':>14} {'GAP(%)':>8} {'Nós':>8}  Status")
    print("-"*90)
    for r in results:
        obj_s   = f"{r['obj']:.4f}"   if r['obj']   is not None else "N/A"
        bnd_s   = f"{r['bound']:.4f}" if r['bound'] is not None else "N/A"
        gap_s   = f"{r['gap_pct']:.4f}" if r['gap_pct'] is not None else "N/A"
        nod_s   = str(r['nodes']) if r['nodes'] is not None else "N/A"
        print(f"{r['instance']:<38} {r['time_s']:>8.1f} {obj_s:>14} {bnd_s:>14} {gap_s:>8} {nod_s:>8}  {r['status']}")

    # Salva sumário consolidado
    summary_path = os.path.join(BASE_DIR, "results_summary.json")
    with open(summary_path, "w") as sf:
        json.dump(results, sf, indent=2)
    print(f"\nSumário consolidado salvo em: {summary_path}")

if __name__ == "__main__":
    main()
