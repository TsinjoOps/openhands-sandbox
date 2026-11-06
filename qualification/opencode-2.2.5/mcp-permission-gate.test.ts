// Candidate integration test for anomalyco/opencode at SHA
// 9bbb8ce18c80f099e0e448775f59d965ead40a21 (v2.2.5).
// Copy to packages/core/test/mcp-permission-gate.test.ts in a separate
// verified upstream checkout. NOT executed or validated yet.
import { expect } from "bun:test"
import { InMemoryTransport } from "@modelcontextprotocol/client"
import { McpServer } from "@modelcontextprotocol/server"
import { Agent } from "@opencode/core/agent"
import { Bus } from "@opencode/core/bus"
import { Credential } from "@opencode/core/credential"
import { Database } from "@opencode/core/database/database"
import { AppNodeBuilder } from "@opencode/core/effect/app-node-builder"
import { Environment } from "@opencode/core/environment/index"
import { Image } from "@opencode/core/image"
import { Integration } from "@opencode/core/integration"
import { Location } from "@opencode/core/location"
import { Mcp } from "@opencode/core/mcp/index"
import { Permission } from "@opencode/core/permission"
import { PermissionSaved } from "@opencode/core/permission/saved"
import { Project } from "@opencode/core/project"
import { ProjectTable } from "@opencode/core/project/sql"
import { Session } from "@opencode/core/session"
import { SessionTable } from "@opencode/core/session/sql"
import { SessionStore } from "@opencode/core/session/store"
import { Tool } from "@opencode/core/tool"
import { McpTool } from "@opencode/core/tool/mcp"
import { LayerNode } from "@opencode/util/effect/layer-node"
import { AbsolutePath } from "@opencode/core/schema"
import { Effect, Layer, Schedule } from "effect"
import { hostEnvironmentLayer } from "./fixture/environment"
import { tempLocationLayer } from "./fixture/location"
import { testEffect } from "./lib/effect"
import { imagePassthrough } from "./lib/image"
import { executeTool, toolIdentity } from "./lib/tool"

const unused = () => Effect.die("integration access is prohibited in this fixture")

const it = testEffect(
  AppNodeBuilder.build(
    LayerNode.group([
      Database.node, Bus.node, SessionStore.node, PermissionSaved.node,
      Agent.node, Permission.node, Tool.node, McpTool.node, Mcp.node,
    ]),
    [
      Location.node.replace(tempLocationLayer),
      Environment.node.replace(hostEnvironmentLayer),
      Integration.node.replace(
        Layer.mock(Integration.Service, {
          revision: () => 0,
          connection: {
            active: unused, resolve: unused, key: unused,
            external: unused, activate: unused, update: unused,
            remove: unused, status: unused,
          },
          oauth: { connect: unused, status: unused, complete: unused, cancel: unused },
          command: { connect: unused, status: unused, cancel: unused },
        }),
      ),
      Credential.node.replace(Layer.mock(Credential.Service, {})),
      Image.node.replace(imagePassthrough),
    ],
  ),
)

const sessionID = Session.ID.make("ses_mcp_permission_225")

const setPermissions = (permissions: Permission.Ruleset) =>
  Effect.gen(function* () {
    const agents = yield* Agent.Service
    yield* agents.transform((editor) =>
      editor.update(Agent.ID.make("build"), (agent) => {
        agent.permissions = [...permissions]
      }),
    )
  })

const setupSession = Effect.gen(function* () {
  const { db } = yield* Database.Service
  yield* db.insert(ProjectTable).values({
    id: Project.ID.global,
    worktree: AbsolutePath.make("/project"),
    sandboxes: [],
  }).onConflictDoNothing().run().pipe(Effect.orDie)
  yield* db.insert(SessionTable).values({
    id: sessionID,
    project_id: Project.ID.global,
    slug: "mcp-permission-gate",
    directory: "/project",
    title: "MCP permission gate",
    version: "2.2.5",
    agent: Agent.ID.make("build"),
  }).onConflictDoNothing().run().pipe(Effect.orDie)
})

const waitForTool = (id: string) =>
  Effect.gen(function* () {
    const registry = yield* Tool.Service
    const registration = yield* McpTool.Service
    yield* registration.flush
    const names = (yield* registry.list()).map((entry) => entry.id)
    if (!names.includes(id)) return yield* Effect.fail("tool not registered")
  }).pipe(Effect.retry({ times: 500, schedule: Schedule.spaced("2 millis") }))

const invoke = () =>
  Effect.gen(function* () {
    const registry = yield* Tool.Service
    return yield* executeTool(registry, {
      sessionID,
      ...toolIdentity,
      call: {
        type: "tool-call",
        id: "call_permission_probe",
        name: "execute",
        input: { code: "return await tools.probe.ping({})" },
      },
    })
  })

it.live("real permission deny blocks MCP before the remote tool is called; allow succeeds", () =>
  Effect.gen(function* () {
    yield* setupSession
    const server = new McpServer({ name: "permission-gate", version: "1.0.0" })
    let calls = 0
    server.registerTool("ping", { description: "counting fixture" }, () => {
      calls += 1
      return { content: [{ type: "text", text: "pong" }] }
    })
    const [client, transport] = InMemoryTransport.createLinkedPair()
    yield* Effect.acquireRelease(
      Effect.promise(() => server.connect(transport)),
      () => Effect.promise(() => server.close()),
    )
    const mcp = yield* Mcp.Service
    yield* mcp.attach("probe", client)
    yield* waitForTool("probe_ping")

    yield* setPermissions([
      { action: "*", resource: "*", effect: "allow" },
      { action: "probe_ping", resource: "*", effect: "deny" },
    ])
    // executeTool() requests an unfiltered Tool.snapshot() through the real
    // OpenCode registry. This intentionally keeps probe_ping visible, so
    // the denial must occur inside Permission.assert(), not catalog filtering.
    const denied = yield* invoke()
    expect(denied.status).toBe("error")
    expect(denied.error).toBeDefined()
    expect(calls).toBe(0)

    yield* setPermissions([{ action: "*", resource: "*", effect: "allow" }])
    const allowed = yield* invoke()
    expect(allowed.status).toBe("completed")
    expect(allowed.output?.output).toBe("pong")
    expect(calls).toBe(1)
  }),
)
