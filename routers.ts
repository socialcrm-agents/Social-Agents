import { router, publicProcedure, protectedProcedure } from './trpc';
import { z } from 'zod';
import { SecurityService } from './backend/services/SecurityService';
import { AICallLogger } from './backend/logger/AICallLogger';
import { OptimizedPromptBuilder } from './backend/services/OptimizedPromptBuilder';
import { EmbeddingSearchService } from './backend/services/EmbeddingSearchService';
import { CacheService } from './backend/services/CacheService';
import { MessageProcessorService } from './backend/services/MessageProcessorService';
import { db } from './db';
import { users, agents, messages, domains, workspaces } from './schema';
import { eq } from 'drizzle-orm';

/**
 * Router principal da aplicação
 * Integra todas as funcionalidades:
 * - Autenticação segura
 * - Processamento de mensagens com logging
 * - Gerenciamento de domínios
 * - Transparência de IA
 */

// ============ AUTH ROUTER ============
export const authRouter = router({
  signup: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string().min(8),
        name: z.string().min(2),
      })
    )
    .mutation(async ({ input }) => {
      try {
        // Validar força da senha
        SecurityService.validatePasswordStrength(input.password);

        // Verificar se email já existe
        const existingUser = await db
          .select()
          .from(users)
          .where(eq(users.email, input.email));

        if (existingUser.length > 0) {
          throw new Error('Email já cadastrado');
        }

        // Hash da senha
        const hashedPassword = await SecurityService.hashPassword(input.password);

        // Criar usuário
        const newUser = await db
          .insert(users)
          .values({
            email: input.email,
            password: hashedPassword,
            name: input.name,
            createdAt: new Date(),
          })
          .returning();

        // Gerar token
        const token = SecurityService.generateToken(newUser[0].id);

        // Log de auditoria
        await AICallLogger.logCall({
          userId: newUser[0].id,
          agentId: null,
          messageText: `Novo usuário criado: ${input.email}`,
          contactPhone: null,
          contactName: input.name,
        });

        return {
          success: true,
          token,
          user: {
            id: newUser[0].id,
            email: newUser[0].email,
            name: newUser[0].name,
          },
        };
      } catch (error) {
        throw new Error(`Erro ao criar usuário: ${error.message}`);
      }
    }),

  login: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const user = await db
          .select()
          .from(users)
          .where(eq(users.email, input.email));

        if (user.length === 0) {
          throw new Error('Usuário não encontrado');
        }

        const isPasswordValid = await SecurityService.verifyPassword(
          input.password,
          user[0].password
        );

        if (!isPasswordValid) {
          throw new Error('Senha incorreta');
        }

        const token = SecurityService.generateToken(user[0].id);

        return {
          success: true,
          token,
          user: {
            id: user[0].id,
            email: user[0].email,
            name: user[0].name,
          },
        };
      } catch (error) {
        throw new Error(`Erro ao fazer login: ${error.message}`);
      }
    }),
});

// ============ AGENT ROUTER ============
export const agentRouter = router({
  create: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        description: z.string(),
        systemPrompt: z.string(),
        workspaceId: z.number(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await db
          .insert(agents)
          .values({
            name: input.name,
            description: input.description,
            systemPrompt: input.systemPrompt,
            workspaceId: input.workspaceId,
            userId: ctx.user.id,
            createdAt: new Date(),
          })
          .returning();

        await AICallLogger.logCall({
          userId: ctx.user.id,
          agentId: agent[0].id,
          messageText: `Agente criado: ${input.name}`,
          contactPhone: null,
          contactName: input.name,
        });

        return agent[0];
      } catch (error) {
        throw new Error(`Erro ao criar agente: ${error.message}`);
      }
    }),

  list: protectedProcedure.query(async ({ ctx }) => {
    try {
      return await db
        .select()
        .from(agents)
        .where(eq(agents.userId, ctx.user.id));
    } catch (error) {
      throw new Error(`Erro ao listar agentes: ${error.message}`);
    }
  }),
});

// ============ MESSAGE ROUTER ============
export const messageRouter = router({
  send: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        messageText: z.string(),
        contactPhone: z.string(),
        contactName: z.string(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        // Log de entrada
        await AICallLogger.logCall({
          userId: ctx.user.id,
          agentId: input.agentId,
          messageText: input.messageText,
          contactPhone: input.contactPhone,
          contactName: input.contactName,
        });

        // Buscar agente
        const agent = await db
          .select()
          .from(agents)
          .where(eq(agents.id, input.agentId));

        if (agent.length === 0) {
          throw new Error('Agente não encontrado');
        }

        // Construir prompt otimizado
        const optimizedPrompt = OptimizedPromptBuilder.build({
          systemPrompt: agent[0].systemPrompt,
          context: `Cliente: ${input.contactName} (${input.contactPhone})`,
          userMessage: input.messageText,
          examples: [],
        });

        // Processar mensagem com cache
        const cacheKey = `msg_${input.agentId}_${input.messageText}`;
        let response = await CacheService.get(cacheKey);

        if (!response) {
          response = await MessageProcessorService.processMessage({
            agentId: input.agentId,
            messageText: input.messageText,
            prompt: optimizedPrompt,
          });

          // Cachear resposta
          await CacheService.set(cacheKey, response, 3600);
        }

        // Salvar mensagem
        const savedMessage = await db
          .insert(messages)
          .values({
            agentId: input.agentId,
            userId: ctx.user.id,
            userMessage: input.messageText,
            aiResponse: response,
            contactPhone: input.contactPhone,
            contactName: input.contactName,
            createdAt: new Date(),
          })
          .returning();

        // Log de saída
        await AICallLogger.logCall({
          userId: ctx.user.id,
          agentId: input.agentId,
          messageText: `Resposta enviada: ${response}`,
          contactPhone: input.contactPhone,
          contactName: input.contactName,
        });

        return {
          success: true,
          message: savedMessage[0],
          response,
        };
      } catch (error) {
        throw new Error(`Erro ao processar mensagem: ${error.message}`);
      }
    }),

  list: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input, ctx }) => {
      try {
        return await db
          .select()
          .from(messages)
          .where(eq(messages.agentId, input.agentId));
      } catch (error) {
        throw new Error(`Erro ao listar mensagens: ${error.message}`);
      }
    }),
});

// ============ DOMAIN ROUTER ============
export const domainRouter = router({
  addDomain: protectedProcedure
    .input(
      z.object({
        workspaceId: z.number(),
        domain: z.string(),
        type: z.enum(['primary', 'secondary']),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const newDomain = await db
          .insert(domains)
          .values({
            workspaceId: input.workspaceId,
            domain: input.domain,
            type: input.type,
            status: 'pending',
            createdAt: new Date(),
          })
          .returning();

        await AICallLogger.logCall({
          userId: ctx.user.id,
          agentId: null,
          messageText: `Domínio adicionado: ${input.domain}`,
          contactPhone: null,
          contactName: input.domain,
        });

        return newDomain[0];
      } catch (error) {
        throw new Error(`Erro ao adicionar domínio: ${error.message}`);
      }
    }),

  listDomains: protectedProcedure
    .input(z.object({ workspaceId: z.number() }))
    .query(async ({ input }) => {
      try {
        return await db
          .select()
          .from(domains)
          .where(eq(domains.workspaceId, input.workspaceId));
      } catch (error) {
        throw new Error(`Erro ao listar domínios: ${error.message}`);
      }
    }),

  verifyDomain: protectedProcedure
    .input(z.object({ domainId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      try {
        // Aqui você implementaria a verificação real de DNS
        const domain = await db
          .select()
          .from(domains)
          .where(eq(domains.id, input.domainId));

        if (domain.length === 0) {
          throw new Error('Domínio não encontrado');
        }

        // Atualizar status
        const updated = await db
          .update(domains)
          .set({ status: 'verified', verifiedAt: new Date() })
          .where(eq(domains.id, input.domainId))
          .returning();

        await AICallLogger.logCall({
          userId: ctx.user.id,
          agentId: null,
          messageText: `Domínio verificado: ${domain[0].domain}`,
          contactPhone: null,
          contactName: domain[0].domain,
        });

        return updated[0];
      } catch (error) {
        throw new Error(`Erro ao verificar domínio: ${error.message}`);
      }
    }),
});

// ============ WORKSPACE ROUTER ============
export const workspaceRouter = router({
  create: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        description: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const workspace = await db
          .insert(workspaces)
          .values({
            name: input.name,
            description: input.description,
            userId: ctx.user.id,
            createdAt: new Date(),
          })
          .returning();

        return workspace[0];
      } catch (error) {
        throw new Error(`Erro ao criar workspace: ${error.message}`);
      }
    }),

  list: protectedProcedure.query(async ({ ctx }) => {
    try {
      return await db
        .select()
        .from(workspaces)
        .where(eq(workspaces.userId, ctx.user.id));
    } catch (error) {
      throw new Error(`Erro ao listar workspaces: ${error.message}`);
    }
  }),
});

// ============ ROOT ROUTER ============
export const appRouter = router({
  auth: authRouter,
  agent: agentRouter,
  message: messageRouter,
  domain: domainRouter,
  workspace: workspaceRouter,
});

export type AppRouter = typeof appRouter;
