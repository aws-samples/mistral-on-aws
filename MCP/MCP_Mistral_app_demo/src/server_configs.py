from mcp import StdioServerParameters
SERVER_CONFIGS = [
        StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-google-maps"],
            env={"GOOGLE_MAPS_API_KEY": "AIzaSyDzizmtrKkTBh_isgFTzO2fsMgK50MdzbI"}
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