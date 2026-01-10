import {
  mysqlTable,
  varchar,
  int,
  text,
  timestamp,
  boolean,
  decimal,
  enum as mysqlEnum,
  index,
} from 'drizzle-orm/mysql-core';
import { relations } from 'drizzle-orm';

/**
 * Schema do banco de dados
 * Integra todas as tabelas necessárias para a plataforma
 * com segurança, auditoria e rastreamento completo
 */

// ============ USERS ============
export const users = mysqlTable(
  'users',
  {
    id: int('id').primaryKey().autoincrement(),
    email: varchar('email', { length: 255 }).unique().notNull(),
    password: varchar('password', { length: 255 }).notNull(),
    name: varchar('name', { length: 255 }).notNull(),
    avatar: varchar('avatar', { length: 255 }),
    emailVerified: boolean('email_verified').default(false),
    emailVerificationToken: varchar('email_verification_token', { length: 255 }),
    emailVerificationExpires: timestamp('email_verification_expires'),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
    lastLoginAt: timestamp('last_login_at'),
    isActive: boolean('is_active').default(true),
  },
  (table) => ({
    emailIdx: index('email_idx').on(table.email),
  })
);

// ============ WORKSPACES ============
export const workspaces = mysqlTable(
  'workspaces',
  {
    id: int('id').primaryKey().autoincrement(),
    userId: int('user_id').notNull(),
    name: varchar('name', { length: 255 }).notNull(),
    description: text('description'),
    logo: varchar('logo', { length: 255 }),
    color: varchar('color', { length: 7 }).default('#FF6B35'),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
  },
  (table) => ({
    userIdIdx: index('user_id_idx').on(table.userId),
  })
);

// ============ DOMAINS ============
export const domains = mysqlTable(
  'domains',
  {
    id: int('id').primaryKey().autoincrement(),
    workspaceId: int('workspace_id').notNull(),
    domain: varchar('domain', { length: 255 }).notNull(),
    type: mysqlEnum('type', ['primary', 'secondary']).default('secondary'),
    status: mysqlEnum('status', ['pending', 'verified', 'active', 'failed']).default('pending'),
    verificationMethod: mysqlEnum('verification_method', ['dns', 'cname', 'file']).default('dns'),
    verificationToken: varchar('verification_token', { length: 255 }),
    verifiedAt: timestamp('verified_at'),
    sslStatus: mysqlEnum('ssl_status', ['pending', 'active', 'expired']).default('pending'),
    sslExpiresAt: timestamp('ssl_expires_at'),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
  },
  (table) => ({
    workspaceIdIdx: index('workspace_id_idx').on(table.workspaceId),
    domainIdx: index('domain_idx').on(table.domain),
  })
);

// ============ AGENTS ============
export const agents = mysqlTable(
  'agents',
  {
    id: int('id').primaryKey().autoincrement(),
    userId: int('user_id').notNull(),
    workspaceId: int('workspace_id').notNull(),
    name: varchar('name', { length: 255 }).notNull(),
    description: text('description'),
    systemPrompt: text('system_prompt').notNull(),
    model: varchar('model', { length: 50 }).default('gpt-4'),
    temperature: decimal('temperature', { precision: 3, scale: 2 }).default('0.7'),
    maxTokens: int('max_tokens').default(2000),
    isActive: boolean('is_active').default(true),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
  },
  (table) => ({
    userIdIdx: index('user_id_idx').on(table.userId),
    workspaceIdIdx: index('workspace_id_idx').on(table.workspaceId),
  })
);

// ============ MESSAGES ============
export const messages = mysqlTable(
  'messages',
  {
    id: int('id').primaryKey().autoincrement(),
    agentId: int('agent_id').notNull(),
    userId: int('user_id').notNull(),
    userMessage: text('user_message').notNull(),
    aiResponse: text('ai_response'),
    contactPhone: varchar('contact_phone', { length: 20 }),
    contactName: varchar('contact_name', { length: 255 }),
    tokenUsed: int('token_used').default(0),
    costUSD: decimal('cost_usd', { precision: 10, scale: 6 }).default('0'),
    source: mysqlEnum('source', ['whatsapp', 'web', 'telegram', 'email']).default('web'),
    status: mysqlEnum('status', ['sent', 'delivered', 'read', 'failed']).default('sent'),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
  },
  (table) => ({
    agentIdIdx: index('agent_id_idx').on(table.agentId),
    userIdIdx: index('user_id_idx').on(table.userId),
    createdAtIdx: index('created_at_idx').on(table.createdAt),
  })
);

// ============ AI CALL LOGS ============
export const aiCallLogs = mysqlTable(
  'ai_call_logs',
  {
    id: int('id').primaryKey().autoincrement(),
    userId: int('user_id').notNull(),
    agentId: int('agent_id'),
    messageText: text('message_text'),
    responseText: text('response_text'),
    contactPhone: varchar('contact_phone', { length: 20 }),
    contactName: varchar('contact_name', { length: 255 }),
    model: varchar('model', { length: 50 }),
    tokensUsed: int('tokens_used').default(0),
    costUSD: decimal('cost_usd', { precision: 10, scale: 6 }).default('0'),
    latencyMs: int('latency_ms').default(0),
    status: mysqlEnum('status', ['success', 'error', 'timeout']).default('success'),
    errorMessage: text('error_message'),
    createdAt: timestamp('created_at').defaultNow(),
  },
  (table) => ({
    userIdIdx: index('user_id_idx').on(table.userId),
    agentIdIdx: index('agent_id_idx').on(table.agentId),
    createdAtIdx: index('created_at_idx').on(table.createdAt),
  })
);

// ============ EMBEDDINGS CACHE ============
export const embeddingsCache = mysqlTable(
  'embeddings_cache',
  {
    id: int('id').primaryKey().autoincrement(),
    agentId: int('agent_id').notNull(),
    query: text('query').notNull(),
    embedding: text('embedding').notNull(), // JSON array
    similarity: decimal('similarity', { precision: 3, scale: 2 }),
    source: varchar('source', { length: 255 }),
    createdAt: timestamp('created_at').defaultNow(),
    expiresAt: timestamp('expires_at'),
  },
  (table) => ({
    agentIdIdx: index('agent_id_idx').on(table.agentId),
    queryIdx: index('query_idx').on(table.query),
  })
);

// ============ WORKSPACE SETTINGS ============
export const workspaceSettings = mysqlTable(
  'workspace_settings',
  {
    id: int('id').primaryKey().autoincrement(),
    workspaceId: int('workspace_id').notNull().unique(),
    openaiApiKey: varchar('openai_api_key', { length: 255 }),
    mercadopagoApiKey: varchar('mercadopago_api_key', { length: 255 }),
    whatsappBusinessId: varchar('whatsapp_business_id', { length: 255 }),
    webhookUrl: varchar('webhook_url', { length: 255 }),
    notificationEmail: varchar('notification_email', { length: 255 }),
    enableLogging: boolean('enable_logging').default(true),
    enableAnalytics: boolean('enable_analytics').default(true),
    createdAt: timestamp('created_at').defaultNow(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow(),
  },
  (table) => ({
    workspaceIdIdx: index('workspace_id_idx').on(table.workspaceId),
  })
);

// ============ AUDIT LOG ============
export const auditLogs = mysqlTable(
  'audit_logs',
  {
    id: int('id').primaryKey().autoincrement(),
    userId: int('user_id').notNull(),
    action: varchar('action', { length: 255 }).notNull(),
    resource: varchar('resource', { length: 255 }),
    resourceId: int('resource_id'),
    changes: text('changes'), // JSON
    ipAddress: varchar('ip_address', { length: 45 }),
    userAgent: text('user_agent'),
    status: mysqlEnum('status', ['success', 'failure']).default('success'),
    createdAt: timestamp('created_at').defaultNow(),
  },
  (table) => ({
    userIdIdx: index('user_id_idx').on(table.userId),
    createdAtIdx: index('created_at_idx').on(table.createdAt),
  })
);

// ============ RELATIONS ============
export const usersRelations = relations(users, ({ many }) => ({
  workspaces: many(workspaces),
  agents: many(agents),
  messages: many(messages),
  aiCallLogs: many(aiCallLogs),
  auditLogs: many(auditLogs),
}));

export const workspacesRelations = relations(workspaces, ({ one, many }) => ({
  user: one(users, {
    fields: [workspaces.userId],
    references: [users.id],
  }),
  domains: many(domains),
  agents: many(agents),
  settings: one(workspaceSettings),
}));

export const domainsRelations = relations(domains, ({ one }) => ({
  workspace: one(workspaces, {
    fields: [domains.workspaceId],
    references: [workspaces.id],
  }),
}));

export const agentsRelations = relations(agents, ({ one, many }) => ({
  user: one(users, {
    fields: [agents.userId],
    references: [users.id],
  }),
  workspace: one(workspaces, {
    fields: [agents.workspaceId],
    references: [workspaces.id],
  }),
  messages: many(messages),
  aiCallLogs: many(aiCallLogs),
  embeddingsCache: many(embeddingsCache),
}));

export const messagesRelations = relations(messages, ({ one }) => ({
  agent: one(agents, {
    fields: [messages.agentId],
    references: [agents.id],
  }),
  user: one(users, {
    fields: [messages.userId],
    references: [users.id],
  }),
}));

export const aiCallLogsRelations = relations(aiCallLogs, ({ one }) => ({
  user: one(users, {
    fields: [aiCallLogs.userId],
    references: [users.id],
  }),
  agent: one(agents, {
    fields: [aiCallLogs.agentId],
    references: [agents.id],
  }),
}));

export const embeddingsCacheRelations = relations(embeddingsCache, ({ one }) => ({
  agent: one(agents, {
    fields: [embeddingsCache.agentId],
    references: [agents.id],
  }),
}));

export const workspaceSettingsRelations = relations(workspaceSettings, ({ one }) => ({
  workspace: one(workspaces, {
    fields: [workspaceSettings.workspaceId],
    references: [workspaces.id],
  }),
}));

export const auditLogsRelations = relations(auditLogs, ({ one }) => ({
  user: one(users, {
    fields: [auditLogs.userId],
    references: [users.id],
  }),
}));
