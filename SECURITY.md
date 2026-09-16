# Security

- Never commit API keys, bearer tokens, cookies, private endpoints, or absolute machine-specific paths.
- Adapters only send lifecycle and display metadata to the local Herdr socket.
- Prompt text is truncated before it is used as a sidebar title.
- Socket and subprocess failures are intentionally ignored so an adapter cannot break the host CLI.
- Review every new adapter's event payload handling for accidental secret disclosure.
