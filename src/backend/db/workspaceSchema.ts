/**
 * workspaceSchema.ts
 * Schema para workspaces e gerenciamento de domínios
 */

import { sqliteTable, text, integer, real, index } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

/**
 * Tabela de Workspaces
 * Cada usuário pode ter múltiplos workspaces
 */
export const workspaces = sqliteTable(
  'workspaces',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    userId: integer('userId').notNull(),
    name: text('name').notNull(),
    slug: text('slug').notNull().unique(), // Para URL: exemplo.com/workspace-slug
    description: text('description'),
    logo: text('logo'), // URL da logo
    color: text('color').default('#3B82F6'), // Cor primária
    timezone: text('timezone').default('America/Sao_Paulo'),
    language: text('language').default('pt-BR'),
    plan: text('plan').default('free'), // free, starter, pro, enterprise
    status: text('status').default('active'), // active, suspended, deleted
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
    updatedAt: integer('updatedAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    userIdIdx: index('workspace_userId_idx').on(table.userId),
    slugIdx: index('workspace_slug_idx').on(table.slug),
  })
);

/**
 * Tabela de Domínios
 * Cada workspace pode ter múltiplos domínios (principal + subdomínios)
 */
export const domains = sqliteTable(
  'domains',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    workspaceId: integer('workspaceId').notNull(),
    domain: text('domain').notNull().unique(), // exemplo.com ou chat.exemplo.com
    type: text('type').notNull(), // 'primary' ou 'subdomain'
    status: text('status').default('pending'), // pending, verified, active, failed, expired
    sslStatus: text('sslStatus').default('pending'), // pending, valid, expired, error
    sslCertificate: text('sslCertificate'), // Certificado SSL
    sslExpiresAt: integer('sslExpiresAt', { mode: 'timestamp' }),
    dnsRecords: text('dnsRecords'), // JSON com registros DNS necessários
    verificationToken: text('verificationToken'), // Token para verificação
    verificationMethod: text('verificationMethod'), // 'dns', 'cname', 'file'
    verifiedAt: integer('verifiedAt', { mode: 'timestamp' }),
    isDefault: integer('isDefault', { mode: 'boolean' }).default(false),
    redirectUrl: text('redirectUrl'), // URL para redirecionar (se aplicável)
    customHeaders: text('customHeaders'), // JSON com headers customizados
    customCss: text('customCss'), // CSS customizado
    customJs: text('customJs'), // JavaScript customizado
    analytics: text('analytics'), // JSON com dados de analytics
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
    updatedAt: integer('updatedAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    workspaceIdIdx: index('domain_workspaceId_idx').on(table.workspaceId),
    domainIdx: index('domain_domain_idx').on(table.domain),
    statusIdx: index('domain_status_idx').on(table.status),
  })
);

/**
 * Tabela de Configurações de Workspace
 * Armazena configurações específicas de cada workspace
 */
export const workspaceSettings = sqliteTable(
  'workspaceSettings',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    workspaceId: integer('workspaceId').notNull().unique(),
    
    // Configurações de Branding
    brandName: text('brandName'),
    brandLogo: text('brandLogo'),
    brandFaviconUrl: text('brandFaviconUrl'),
    brandPrimaryColor: text('brandPrimaryColor').default('#3B82F6'),
    brandSecondaryColor: text('brandSecondaryColor').default('#1F2937'),
    brandFontFamily: text('brandFontFamily').default('Inter, sans-serif'),
    
    // Configurações de Email
    emailFrom: text('emailFrom'),
    emailFromName: text('emailFromName'),
    smtpHost: text('smtpHost'),
    smtpPort: integer('smtpPort'),
    smtpUser: text('smtpUser'),
    smtpPassword: text('smtpPassword'), // Criptografado
    
    // Configurações de Segurança
    requireHttps: integer('requireHttps', { mode: 'boolean' }).default(true),
    enableCors: integer('enableCors', { mode: 'boolean' }).default(true),
    corsOrigins: text('corsOrigins'), // JSON array
    enableRateLimit: integer('enableRateLimit', { mode: 'boolean' }).default(true),
    rateLimitRequests: integer('rateLimitRequests').default(100),
    rateLimitWindow: integer('rateLimitWindow').default(60), // segundos
    
    // Configurações de Integração
    webhookUrl: text('webhookUrl'),
    webhookSecret: text('webhookSecret'),
    apiKeyPrefix: text('apiKeyPrefix').default('sk_live_'),
    
    // Configurações de Dados
    dataRetentionDays: integer('dataRetentionDays').default(90),
    enableBackup: integer('enableBackup', { mode: 'boolean' }).default(true),
    backupFrequency: text('backupFrequency').default('daily'), // daily, weekly, monthly
    
    // Configurações de Notificação
    notifyOnError: integer('notifyOnError', { mode: 'boolean' }).default(true),
    notifyEmail: text('notifyEmail'),
    notifySlack: text('notifySlack'), // Webhook do Slack
    
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
    updatedAt: integer('updatedAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    workspaceIdIdx: index('settings_workspaceId_idx').on(table.workspaceId),
  })
);

/**
 * Tabela de Membros do Workspace
 * Controle de acesso e permissões
 */
export const workspaceMembers = sqliteTable(
  'workspaceMembers',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    workspaceId: integer('workspaceId').notNull(),
    userId: integer('userId').notNull(),
    role: text('role').notNull(), // 'owner', 'admin', 'member', 'viewer'
    permissions: text('permissions'), // JSON array de permissões customizadas
    status: text('status').default('active'), // active, invited, suspended
    invitedAt: integer('invitedAt', { mode: 'timestamp' }),
    invitedBy: integer('invitedBy'),
    acceptedAt: integer('acceptedAt', { mode: 'timestamp' }),
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
    updatedAt: integer('updatedAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    workspaceIdIdx: index('members_workspaceId_idx').on(table.workspaceId),
    userIdIdx: index('members_userId_idx').on(table.userId),
  })
);

/**
 * Tabela de Auditoria de Domínios
 * Registra todas as mudanças em domínios
 */
export const domainAuditLog = sqliteTable(
  'domainAuditLog',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    domainId: integer('domainId').notNull(),
    workspaceId: integer('workspaceId').notNull(),
    action: text('action').notNull(), // 'created', 'verified', 'updated', 'deleted', 'ssl_renewed'
    changedBy: integer('changedBy').notNull(),
    oldValue: text('oldValue'), // JSON
    newValue: text('newValue'), // JSON
    reason: text('reason'),
    ipAddress: text('ipAddress'),
    userAgent: text('userAgent'),
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    domainIdIdx: index('audit_domainId_idx').on(table.domainId),
    workspaceIdIdx: index('audit_workspaceId_idx').on(table.workspaceId),
  })
);

/**
 * Tabela de Certificados SSL
 * Gerenciamento de certificados SSL/TLS
 */
export const sslCertificates = sqliteTable(
  'sslCertificates',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    domainId: integer('domainId').notNull(),
    workspaceId: integer('workspaceId').notNull(),
    certificate: text('certificate').notNull(), // Certificado PEM
    privateKey: text('privateKey').notNull(), // Chave privada (criptografada)
    issuer: text('issuer'),
    subject: text('subject'),
    issuedAt: integer('issuedAt', { mode: 'timestamp' }),
    expiresAt: integer('expiresAt', { mode: 'timestamp' }),
    autoRenew: integer('autoRenew', { mode: 'boolean' }).default(true),
    renewalDate: integer('renewalDate', { mode: 'timestamp' }),
    status: text('status').default('active'), // active, expired, revoked
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
    updatedAt: integer('updatedAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    domainIdIdx: index('ssl_domainId_idx').on(table.domainId),
    workspaceIdIdx: index('ssl_workspaceId_idx').on(table.workspaceId),
  })
);

/**
 * Tabela de Estatísticas de Domínio
 * Rastreia uso e performance de cada domínio
 */
export const domainStats = sqliteTable(
  'domainStats',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    domainId: integer('domainId').notNull(),
    workspaceId: integer('workspaceId').notNull(),
    date: text('date').notNull(), // YYYY-MM-DD
    
    // Tráfego
    totalRequests: integer('totalRequests').default(0),
    totalErrors: integer('totalErrors').default(0),
    totalLatency: real('totalLatency').default(0), // ms
    
    // Usuários
    uniqueVisitors: integer('uniqueVisitors').default(0),
    returningVisitors: integer('returningVisitors').default(0),
    
    // Performance
    avgResponseTime: real('avgResponseTime').default(0), // ms
    p95ResponseTime: real('p95ResponseTime').default(0), // ms
    p99ResponseTime: real('p99ResponseTime').default(0), // ms
    
    // Uptime
    uptime: real('uptime').default(100), // percentual
    downtime: integer('downtime').default(0), // segundos
    
    createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
  },
  table => ({
    domainIdIdx: index('stats_domainId_idx').on(table.domainId),
    dateIdx: index('stats_date_idx').on(table.date),
  })
);

export type Workspace = typeof workspaces.$inferSelect;
export type Domain = typeof domains.$inferSelect;
export type WorkspaceSettings = typeof workspaceSettings.$inferSelect;
export type WorkspaceMember = typeof workspaceMembers.$inferSelect;
export type DomainAuditLog = typeof domainAuditLog.$inferSelect;
export type SSLCertificate = typeof sslCertificates.$inferSelect;
export type DomainStats = typeof domainStats.$inferSelect;
