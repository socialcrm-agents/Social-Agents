/**
 * domainRouter.ts
 * Router para gerenciamento de domínios e workspaces
 */

import { router, protectedProcedure } from '../trpc';
import { z } from 'zod';
import { TRPCError } from '@trpc/server';
import * as db from '../db';
import SecurityService from '../services/SecurityService';

// ============================================================================
// SCHEMAS DE VALIDAÇÃO
// ============================================================================

const createWorkspaceSchema = z.object({
  name: z.string().min(2).max(100),
  slug: z.string().min(2).max(50).regex(/^[a-z0-9-]+$/),
  description: z.string().optional(),
  color: z.string().regex(/^#[0-9A-F]{6}$/i).optional(),
});

const updateWorkspaceSchema = z.object({
  workspaceId: z.number(),
  name: z.string().min(2).max(100).optional(),
  description: z.string().optional(),
  color: z.string().regex(/^#[0-9A-F]{6}$/i).optional(),
});

const addDomainSchema = z.object({
  workspaceId: z.number(),
  domain: z.string().regex(/^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i),
  type: z.enum(['primary', 'subdomain']),
});

const verifyDomainSchema = z.object({
  domainId: z.number(),
  verificationMethod: z.enum(['dns', 'cname', 'file']),
});

const updateDomainSettingsSchema = z.object({
  domainId: z.number(),
  customCss: z.string().optional(),
  customJs: z.string().optional(),
  customHeaders: z.record(z.string()).optional(),
  redirectUrl: z.string().url().optional(),
});

const updateWorkspaceSettingsSchema = z.object({
  workspaceId: z.number(),
  brandName: z.string().optional(),
  brandPrimaryColor: z.string().optional(),
  emailFrom: z.string().email().optional(),
  webhookUrl: z.string().url().optional(),
  enableRateLimit: z.boolean().optional(),
  rateLimitRequests: z.number().min(1).optional(),
});

// ============================================================================
// ROUTER DE DOMÍNIOS
// ============================================================================

export const domainRouter = router({
  /**
   * Criar novo workspace
   */
  createWorkspace: protectedProcedure
    .input(createWorkspaceSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Validar slug único
        const existingWorkspace = await db.query.workspaces.findFirst({
          where: eq(workspaces.slug, input.slug),
        });

        if (existingWorkspace) {
          throw new TRPCError({
            code: 'CONFLICT',
            message: 'Slug já existe',
          });
        }

        // 2. Criar workspace
        const workspace = await db.insert(workspaces).values({
          userId: ctx.user.id,
          name: input.name,
          slug: input.slug,
          description: input.description,
          color: input.color,
        });

        // 3. Criar configurações padrão
        await db.insert(workspaceSettings).values({
          workspaceId: workspace.id,
          brandName: input.name,
          brandPrimaryColor: input.color,
        });

        // 4. Adicionar usuário como owner
        await db.insert(workspaceMembers).values({
          workspaceId: workspace.id,
          userId: ctx.user.id,
          role: 'owner',
        });

        console.log(`[Domain] Workspace criado: ${workspace.id} (${input.slug})`);

        return {
          success: true,
          workspace: {
            id: workspace.id,
            name: workspace.name,
            slug: workspace.slug,
          },
        };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao criar workspace:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao criar workspace',
        });
      }
    }),

  /**
   * Listar workspaces do usuário
   */
  listWorkspaces: protectedProcedure.query(async ({ ctx }) => {
    try {
      const workspaceList = await db.query.workspaceMembers.findMany({
        where: eq(workspaceMembers.userId, ctx.user.id),
        with: {
          workspace: true,
        },
      });

      return workspaceList.map(m => ({
        id: m.workspace.id,
        name: m.workspace.name,
        slug: m.workspace.slug,
        role: m.role,
        plan: m.workspace.plan,
        status: m.workspace.status,
      }));
    } catch (error) {
      console.error('[Domain] Erro ao listar workspaces:', error);
      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Erro ao listar workspaces',
      });
    }
  }),

  /**
   * Obter detalhes do workspace
   */
  getWorkspace: protectedProcedure
    .input(z.object({ workspaceId: z.number() }))
    .query(async ({ input, ctx }) => {
      try {
        // 1. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, input.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para acessar este workspace',
          });
        }

        // 2. Buscar workspace
        const workspace = await db.query.workspaces.findFirst({
          where: eq(workspaces.id, input.workspaceId),
          with: {
            domains: true,
            settings: true,
          },
        });

        if (!workspace) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Workspace não encontrado',
          });
        }

        return workspace;
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao obter workspace:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao obter workspace',
        });
      }
    }),

  /**
   * Atualizar workspace
   */
  updateWorkspace: protectedProcedure
    .input(updateWorkspaceSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Verificar permissão (owner ou admin)
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, input.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member || !['owner', 'admin'].includes(member.role)) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para atualizar este workspace',
          });
        }

        // 2. Atualizar workspace
        await db
          .update(workspaces)
          .set({
            name: input.name,
            description: input.description,
            color: input.color,
            updatedAt: new Date(),
          })
          .where(eq(workspaces.id, input.workspaceId));

        console.log(`[Domain] Workspace atualizado: ${input.workspaceId}`);

        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao atualizar workspace:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao atualizar workspace',
        });
      }
    }),

  /**
   * Adicionar domínio ao workspace
   */
  addDomain: protectedProcedure
    .input(addDomainSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, input.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member || !['owner', 'admin'].includes(member.role)) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para adicionar domínios',
          });
        }

        // 2. Validar domínio único
        const existingDomain = await db.query.domains.findFirst({
          where: eq(domains.domain, input.domain),
        });

        if (existingDomain) {
          throw new TRPCError({
            code: 'CONFLICT',
            message: 'Domínio já está em uso',
          });
        }

        // 3. Gerar token de verificação
        const verificationToken = SecurityService.generateSecureToken();

        // 4. Gerar registros DNS
        const dnsRecords = generateDNSRecords(input.domain, verificationToken);

        // 5. Criar domínio
        const domain = await db.insert(domains).values({
          workspaceId: input.workspaceId,
          domain: input.domain,
          type: input.type,
          status: 'pending',
          verificationToken,
          verificationMethod: 'dns',
          dnsRecords: JSON.stringify(dnsRecords),
        });

        // 6. Registrar auditoria
        await db.insert(domainAuditLog).values({
          domainId: domain.id,
          workspaceId: input.workspaceId,
          action: 'created',
          changedBy: ctx.user.id,
          newValue: JSON.stringify({ domain: input.domain, type: input.type }),
          ipAddress: ctx.req.ip,
        });

        console.log(`[Domain] Domínio adicionado: ${input.domain}`);

        return {
          success: true,
          domain: {
            id: domain.id,
            domain: input.domain,
            status: 'pending',
            dnsRecords,
            verificationToken,
          },
        };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao adicionar domínio:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao adicionar domínio',
        });
      }
    }),

  /**
   * Listar domínios do workspace
   */
  listDomains: protectedProcedure
    .input(z.object({ workspaceId: z.number() }))
    .query(async ({ input, ctx }) => {
      try {
        // 1. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, input.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para acessar este workspace',
          });
        }

        // 2. Listar domínios
        const domainList = await db.query.domains.findMany({
          where: eq(domains.workspaceId, input.workspaceId),
        });

        return domainList;
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao listar domínios:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao listar domínios',
        });
      }
    }),

  /**
   * Verificar domínio
   */
  verifyDomain: protectedProcedure
    .input(verifyDomainSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Buscar domínio
        const domain = await db.query.domains.findFirst({
          where: eq(domains.id, input.domainId),
        });

        if (!domain) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Domínio não encontrado',
          });
        }

        // 2. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, domain.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member || !['owner', 'admin'].includes(member.role)) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para verificar este domínio',
          });
        }

        // 3. Verificar DNS (simulado)
        const isVerified = await verifyDNSRecord(domain.domain, domain.verificationToken);

        if (!isVerified) {
          throw new TRPCError({
            code: 'BAD_REQUEST',
            message: 'Registro DNS não encontrado. Verifique a configuração.',
          });
        }

        // 4. Atualizar status
        await db
          .update(domains)
          .set({
            status: 'verified',
            verifiedAt: new Date(),
            updatedAt: new Date(),
          })
          .where(eq(domains.id, input.domainId));

        // 5. Registrar auditoria
        await db.insert(domainAuditLog).values({
          domainId: input.domainId,
          workspaceId: domain.workspaceId,
          action: 'verified',
          changedBy: ctx.user.id,
          ipAddress: ctx.req.ip,
        });

        console.log(`[Domain] Domínio verificado: ${domain.domain}`);

        return { success: true, message: 'Domínio verificado com sucesso' };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao verificar domínio:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao verificar domínio',
        });
      }
    }),

  /**
   * Atualizar configurações do domínio
   */
  updateDomainSettings: protectedProcedure
    .input(updateDomainSettingsSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Buscar domínio
        const domain = await db.query.domains.findFirst({
          where: eq(domains.id, input.domainId),
        });

        if (!domain) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Domínio não encontrado',
          });
        }

        // 2. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, domain.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member || !['owner', 'admin'].includes(member.role)) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para atualizar este domínio',
          });
        }

        // 3. Atualizar configurações
        await db
          .update(domains)
          .set({
            customCss: input.customCss,
            customJs: input.customJs,
            customHeaders: input.customHeaders ? JSON.stringify(input.customHeaders) : undefined,
            redirectUrl: input.redirectUrl,
            updatedAt: new Date(),
          })
          .where(eq(domains.id, input.domainId));

        // 4. Registrar auditoria
        await db.insert(domainAuditLog).values({
          domainId: input.domainId,
          workspaceId: domain.workspaceId,
          action: 'updated',
          changedBy: ctx.user.id,
          oldValue: JSON.stringify({
            customCss: domain.customCss,
            customJs: domain.customJs,
          }),
          newValue: JSON.stringify({
            customCss: input.customCss,
            customJs: input.customJs,
          }),
          ipAddress: ctx.req.ip,
        });

        console.log(`[Domain] Configurações atualizadas: ${domain.domain}`);

        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao atualizar configurações:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao atualizar configurações',
        });
      }
    }),

  /**
   * Atualizar configurações do workspace
   */
  updateWorkspaceSettings: protectedProcedure
    .input(updateWorkspaceSettingsSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, input.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member || !['owner', 'admin'].includes(member.role)) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para atualizar configurações',
          });
        }

        // 2. Atualizar configurações
        await db
          .update(workspaceSettings)
          .set({
            brandName: input.brandName,
            brandPrimaryColor: input.brandPrimaryColor,
            emailFrom: input.emailFrom,
            webhookUrl: input.webhookUrl,
            enableRateLimit: input.enableRateLimit,
            rateLimitRequests: input.rateLimitRequests,
            updatedAt: new Date(),
          })
          .where(eq(workspaceSettings.workspaceId, input.workspaceId));

        console.log(`[Domain] Configurações do workspace atualizadas: ${input.workspaceId}`);

        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao atualizar configurações:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao atualizar configurações',
        });
      }
    }),

  /**
   * Obter estatísticas do domínio
   */
  getDomainStats: protectedProcedure
    .input(z.object({ domainId: z.number(), days: z.number().default(30) }))
    .query(async ({ input, ctx }) => {
      try {
        // 1. Buscar domínio
        const domain = await db.query.domains.findFirst({
          where: eq(domains.id, input.domainId),
        });

        if (!domain) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Domínio não encontrado',
          });
        }

        // 2. Verificar permissão
        const member = await db.query.workspaceMembers.findFirst({
          where: and(
            eq(workspaceMembers.workspaceId, domain.workspaceId),
            eq(workspaceMembers.userId, ctx.user.id)
          ),
        });

        if (!member) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Sem permissão para acessar este domínio',
          });
        }

        // 3. Buscar estatísticas
        const stats = await db.query.domainStats.findMany({
          where: and(
            eq(domainStats.domainId, input.domainId),
            gte(domainStats.date, getDateNDaysAgo(input.days))
          ),
        });

        return stats;
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Domain] Erro ao obter estatísticas:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao obter estatísticas',
        });
      }
    }),
});

// ============================================================================
// FUNÇÕES AUXILIARES
// ============================================================================

/**
 * Gerar registros DNS para verificação
 */
function generateDNSRecords(domain: string, token: string) {
  return {
    cname: {
      name: `_verify.${domain}`,
      value: `verify-${token}.example.com`,
      ttl: 3600,
    },
    txt: {
      name: domain,
      value: `verification=${token}`,
      ttl: 3600,
    },
  };
}

/**
 * Verificar registro DNS (simulado)
 */
async function verifyDNSRecord(domain: string, token: string): Promise<boolean> {
  try {
    // Implementar verificação real de DNS aqui
    // Por enquanto, retornar true para teste
    console.log(`[Domain] Verificando DNS para ${domain}`);
    return true;
  } catch (error) {
    console.error('[Domain] Erro ao verificar DNS:', error);
    return false;
  }
}

/**
 * Obter data de N dias atrás
 */
function getDateNDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().split('T')[0];
}

export default domainRouter;
