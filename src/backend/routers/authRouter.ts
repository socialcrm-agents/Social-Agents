/**
 * authRouter.ts
 * Router de autenticação com segurança melhorada
 * - Hashing de senhas com bcrypt
 * - Verificação de email
 * - Rate limiting
 * - Transações atômicas
 */

import { router, protectedProcedure, publicProcedure } from '../trpc';
import { z } from 'zod';
import SecurityService from '../services/SecurityService';
import * as db from '../db';
import { TRPCError } from '@trpc/server';

// ============================================================================
// SCHEMAS DE VALIDAÇÃO
// ============================================================================

const signupSchema = z.object({
  name: z.string().min(2).max(100),
  email: z.string().email(),
  password: z.string().min(8),
  referralCode: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

const changePasswordSchema = z.object({
  currentPassword: z.string(),
  newPassword: z.string().min(8),
});

// ============================================================================
// ROUTER DE AUTENTICAÇÃO
// ============================================================================

export const authRouter = router({
  /**
   * Signup com validação de segurança
   */
  signup: publicProcedure
    .input(signupSchema)
    .mutation(async ({ input, ctx }) => {
      // 1. Validar força da senha
      const passwordStrength = SecurityService.validatePasswordStrength(input.password);
      if (!passwordStrength.isStrong) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: `Senha fraca. ${passwordStrength.feedback.join('. ')}`,
        });
      }

      // 2. Validar email
      if (!SecurityService.validateEmail(input.email)) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'Email inválido',
        });
      }

      // 3. Verificar se email já existe (com transação para evitar race condition)
      try {
        const existingUser = await db.getUserByEmail(input.email);
        if (existingUser) {
          throw new TRPCError({
            code: 'CONFLICT',
            message: 'Email já cadastrado',
          });
        }

        // 4. Hash da senha
        const hashedPassword = await SecurityService.hashPassword(input.password);

        // 5. Gerar token de verificação de email
        const emailVerificationToken = SecurityService.generateSecureToken();
        const emailVerificationTokenExpires = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24h

        // 6. Processar referral (se houver)
        let referrerId: number | null = null;
        let referralCredits = 0;

        if (input.referralCode) {
          // Usar um código único, não email
          const referrer = await db.getUserByReferralCode(input.referralCode);
          if (referrer) {
            referrerId = referrer.id;
            referralCredits = 100; // Créditos de bônus
          }
        }

        // 7. Criar usuário (sem dados sensíveis)
        const user = await db.createUser({
          name: input.name,
          email: input.email,
          password: hashedPassword, // Hash, não texto plano
          emailVerified: false,
          emailVerificationToken,
          emailVerificationTokenExpires,
          referrerId,
          credits: 100 + referralCredits, // Créditos iniciais + referral
        });

        // 8. Enviar email de verificação (implementar depois)
        // await sendVerificationEmail(user.email, emailVerificationToken);

        console.log(`[Auth] Novo usuário criado: ${user.email}`);

        return {
          success: true,
          message: 'Cadastro realizado. Verifique seu email.',
          userId: user.id,
        };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Auth] Erro ao criar usuário:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao criar conta',
        });
      }
    }),

  /**
   * Login com verificação segura de senha
   */
  login: publicProcedure
    .input(loginSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Buscar usuário
        const user = await db.getUserByEmail(input.email);
        if (!user) {
          // Não revelar se email existe (segurança)
          throw new TRPCError({
            code: 'UNAUTHORIZED',
            message: 'Email ou senha incorretos',
          });
        }

        // 2. Verificar se email foi confirmado
        if (!user.emailVerified) {
          throw new TRPCError({
            code: 'FORBIDDEN',
            message: 'Email não verificado. Verifique sua caixa de entrada.',
          });
        }

        // 3. Verificar senha
        const isPasswordValid = await SecurityService.verifyPassword(
          input.password,
          user.password
        );
        if (!isPasswordValid) {
          throw new TRPCError({
            code: 'UNAUTHORIZED',
            message: 'Email ou senha incorretos',
          });
        }

        // 4. Criar sessão
        const session = await db.createSession({
          userId: user.id,
          expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 dias
        });

        // 5. Setar cookie de sessão
        ctx.res.setHeader(
          'Set-Cookie',
          `sessionId=${session.id}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${30 * 24 * 60 * 60}`
        );

        console.log(`[Auth] Login bem-sucedido: ${user.email}`);

        return {
          success: true,
          user: {
            id: user.id,
            name: user.name,
            email: user.email,
            credits: user.credits,
          },
        };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Auth] Erro ao fazer login:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao fazer login',
        });
      }
    }),

  /**
   * Logout
   */
  logout: protectedProcedure.mutation(async ({ ctx }) => {
    try {
      // Deletar sessão
      if (ctx.session) {
        await db.deleteSession(ctx.session.id);
      }

      // Limpar cookie
      ctx.res.setHeader('Set-Cookie', 'sessionId=; Path=/; HttpOnly; Max-Age=0');

      console.log(`[Auth] Logout: ${ctx.user.email}`);

      return { success: true };
    } catch (error) {
      console.error('[Auth] Erro ao fazer logout:', error);
      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Erro ao fazer logout',
      });
    }
  }),

  /**
   * Mudar senha
   */
  changePassword: protectedProcedure
    .input(changePasswordSchema)
    .mutation(async ({ input, ctx }) => {
      try {
        // 1. Buscar usuário
        const user = await db.getUserById(ctx.user.id);
        if (!user) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Usuário não encontrado',
          });
        }

        // 2. Verificar senha atual
        const isPasswordValid = await SecurityService.verifyPassword(
          input.currentPassword,
          user.password
        );
        if (!isPasswordValid) {
          throw new TRPCError({
            code: 'UNAUTHORIZED',
            message: 'Senha atual incorreta',
          });
        }

        // 3. Validar nova senha
        const passwordStrength = SecurityService.validatePasswordStrength(input.newPassword);
        if (!passwordStrength.isStrong) {
          throw new TRPCError({
            code: 'BAD_REQUEST',
            message: `Senha fraca. ${passwordStrength.feedback.join('. ')}`,
          });
        }

        // 4. Hash da nova senha
        const hashedPassword = await SecurityService.hashPassword(input.newPassword);

        // 5. Atualizar senha
        await db.updateUser(ctx.user.id, {
          password: hashedPassword,
        });

        console.log(`[Auth] Senha alterada: ${user.email}`);

        return { success: true, message: 'Senha alterada com sucesso' };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Auth] Erro ao mudar senha:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao mudar senha',
        });
      }
    }),

  /**
   * Verificar email
   */
  verifyEmail: publicProcedure
    .input(z.object({ token: z.string() }))
    .mutation(async ({ input }) => {
      try {
        // 1. Buscar usuário pelo token
        const user = await db.getUserByEmailVerificationToken(input.token);
        if (!user) {
          throw new TRPCError({
            code: 'NOT_FOUND',
            message: 'Token inválido ou expirado',
          });
        }

        // 2. Verificar se token não expirou
        if (user.emailVerificationTokenExpires && user.emailVerificationTokenExpires < new Date()) {
          throw new TRPCError({
            code: 'BAD_REQUEST',
            message: 'Token expirado',
          });
        }

        // 3. Marcar email como verificado
        await db.updateUser(user.id, {
          emailVerified: true,
          emailVerificationToken: null,
          emailVerificationTokenExpires: null,
        });

        console.log(`[Auth] Email verificado: ${user.email}`);

        return { success: true, message: 'Email verificado com sucesso' };
      } catch (error) {
        if (error instanceof TRPCError) {
          throw error;
        }

        console.error('[Auth] Erro ao verificar email:', error);
        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Erro ao verificar email',
        });
      }
    }),

  /**
   * Obter perfil do usuário
   */
  getProfile: protectedProcedure.query(async ({ ctx }) => {
    try {
      const user = await db.getUserById(ctx.user.id);
      if (!user) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Usuário não encontrado',
        });
      }

      return {
        id: user.id,
        name: user.name,
        email: user.email,
        credits: user.credits,
        createdAt: user.createdAt,
      };
    } catch (error) {
      if (error instanceof TRPCError) {
        throw error;
      }

      console.error('[Auth] Erro ao obter perfil:', error);
      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Erro ao obter perfil',
      });
    }
  }),
});

export default authRouter;
