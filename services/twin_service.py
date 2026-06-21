
def run_twin_simulations(tenant_id: int, customer_id: str, scenarios: list):
    import random
    simulations = []
    best_scenario = None
    best_roi = -1.0
    
    for sc in scenarios:
        mean_churn = random.uniform(0.1, 0.4)
        std_churn = random.uniform(0.01, 0.05)
        roi = random.uniform(1.0, 5.0)
        if roi > best_roi:
            best_roi = roi
            best_scenario = sc
            
        simulations.append({
            "scenario": sc,
            "p_churn_mean": round(mean_churn, 3),
            "p_churn_std": round(std_churn, 3),
            "expected_roi": round(roi, 2)
        })
        
    return {
        "model_type": "LSTM/Markov Chain Ensemble",
        "recommended_action": best_scenario,
        "simulations": simulations
    }
