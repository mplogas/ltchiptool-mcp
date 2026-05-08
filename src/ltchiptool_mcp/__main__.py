"""Allow running as: python -m ltchiptool_mcp"""

from ltchiptool_mcp.server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
