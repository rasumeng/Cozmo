from langchain_ollama import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain import hub

# Step 1: Load the local model via Ollama
llm = OllamaLLM(model="phi3")

# Step 2: Define a simple tool -- a calculator
@tool
def calculator(expression: str) -> str:
    """Evaluates a basic math expression. Input should be a valid Python math expression."""
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"

# Step 3: Bundle tools together
tools = [calculator]

# Step 4: Load a ReAct prompt template (Reason + Act pattern)
prompt = hub.pull("hwchase17/react")

# Step 5: Create the agent
agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

# Step 6: Wrap in an executor to handle the agent loop
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Step 7: Run the agent
response = agent_executor.invoke({
    "input": "What is 245 multiplied by 18, and then divided by 5?"
})

print("\n--- Agent Response ---")
print(response["output"])