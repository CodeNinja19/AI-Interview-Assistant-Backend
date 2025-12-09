import pandas as pd
from langchain_core.tools import tool 
# Load data once (replace with your actual CSV file)
df = pd.read_csv("agri_data.csv")

@tool
def search_data(state=None, district=None, market=None, commodity=None, variety=None):
    """
    Search agricultural market data by multiple filters.
    
    Args:
        state (str): State name
        district (str): District name
        market (str): Market name
        commodity (str): Commodity name
        variety (str): Variety name
    
    Returns:
        pd.DataFrame: Filtered results (top 10 rows)
    """
    results = df.copy()
    print("here")
    if state:
        results = results[results["state"].str.lower() == state.lower()]
    if district:
        results = results[results["district"].str.lower() == district.lower()]
    if market:
        results = results[results["market"].str.lower() == market.lower()]
    if commodity:
        results = results[results["commodity"].str.lower() == commodity.lower()]
    if variety:
        results = results[results["variety"].str.lower() == variety.lower()]
    
    return results.head(10).to_string(index=False) 
