# Campus Customs Ops Desk (frontend)

React + Vite + TypeScript dashboard for the Campus Customs agent team.

```
npm install
npm run dev          # opens http://localhost:5173
```

- The board calls the FastAPI backend at `VITE_API_URL` (set in `.env.development`; the default is `http://localhost:8000`). Start the backend first. See the root `README.md`.
- On Windows PowerShell, if `npm` is blocked by the script policy, use `npm.cmd run dev`.
- Design notes are in `../output/design.md`.

| File | What it is |
|---|---|
| `src/App.tsx` | Layout, polling, run, approve and reset actions |
| `src/api.ts` | Typed calls to the backend routes |
| `src/agents.ts` | Agent colors, badges and ticket types |
| `src/components/TicketList.tsx` | Ticket board |
| `src/components/AgentStage.tsx` | The five agents (working, on this ticket, not called) and hand-offs |
| `src/components/Feed.tsx` | Live agent conversation with MCP tool chips |
| `src/components/Summary.tsx` | The Boss's final call, what each agent did, and drafts |
| `src/components/SidePanels.tsx` | Checking balance and the approval queue |
