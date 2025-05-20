from mcp import StdioServerParameters
SERVER_CONFIGS = [
        StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-google-maps"],
            env={"GOOGLE_MAPS_API_KEY": "<ADD_GOOGLE_MAP_API>"}
        ),
        StdioServerParameters(
            command="npx",
            args=["-y", "time-mcp"],
        ),
        StdioServerParameters(
            command="npx",
            args=["@modelcontextprotocol/server-memory"]
            )
    ]