/**
 * RateLimitMiddleware.ts
 * Middleware de rate limiting para proteção contra:
 * - Brute force attacks
 * - DDoS
 * - Abuso de API
 */

import { Request, Response, NextFunction } from 'express';

interface RateLimitConfig {
  windowMs: number; // Janela de tempo em ms
  maxRequests: number; // Máximo de requisições por janela
  message?: string;
  skipSuccessfulRequests?: boolean;
  skipFailedRequests?: boolean;
}

interface RequestRecord {
  count: number;
  resetTime: number;
}

class RateLimiter {
  private store: Map<string, RequestRecord> = new Map();
  private config: RateLimitConfig;

  constructor(config: RateLimitConfig) {
    this.config = {
      windowMs: 60 * 1000, // 1 minuto por padrão
      maxRequests: 100,
      message: 'Muitas requisições. Tente novamente mais tarde.',
      skipSuccessfulRequests: false,
      skipFailedRequests: false,
      ...config,
    };

    // Limpar registos expirados a cada 5 minutos
    setInterval(() => this.cleanupExpiredRecords(), 5 * 60 * 1000);
  }

  /**
   * Middleware para Express
   */
  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      const key = this.getKey(req);
      const now = Date.now();

      // Obter ou criar registro
      let record = this.store.get(key);

      if (!record || now > record.resetTime) {
        record = {
          count: 0,
          resetTime: now + this.config.windowMs,
        };
      }

      record.count++;
      this.store.set(key, record);

      // Adicionar headers
      res.set('X-RateLimit-Limit', String(this.config.maxRequests));
      res.set('X-RateLimit-Remaining', String(Math.max(0, this.config.maxRequests - record.count)));
      res.set('X-RateLimit-Reset', String(record.resetTime));

      // Verificar limite
      if (record.count > this.config.maxRequests) {
        console.warn(
          `[RateLimit] Limite excedido para ${key} | Requisições: ${record.count}/${this.config.maxRequests}`
        );

        return res.status(429).json({
          error: 'Too Many Requests',
          message: this.config.message,
          retryAfter: Math.ceil((record.resetTime - now) / 1000),
        });
      }

      next();
    };
  }

  /**
   * Obter chave de identificação (IP + endpoint)
   */
  private getKey(req: Request): string {
    const ip = req.ip || req.socket.remoteAddress || 'unknown';
    const endpoint = req.path;
    return `${ip}:${endpoint}`;
  }

  /**
   * Limpar registos expirados
   */
  private cleanupExpiredRecords(): void {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, record] of this.store.entries()) {
      if (now > record.resetTime) {
        this.store.delete(key);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      console.log(`[RateLimit] Limpeza: ${cleaned} registos expirados removidos`);
    }
  }

  /**
   * Resetar limite para um cliente específico
   */
  reset(key: string): void {
    this.store.delete(key);
    console.log(`[RateLimit] Limite resetado para ${key}`);
  }

  /**
   * Obter status do rate limiter
   */
  getStatus(): {
    activeKeys: number;
    totalRequests: number;
  } {
    let totalRequests = 0;
    for (const record of this.store.values()) {
      totalRequests += record.count;
    }

    return {
      activeKeys: this.store.size,
      totalRequests,
    };
  }
}

/**
 * Configurações pré-definidas de rate limiting
 */
export const RateLimitConfigs = {
  // Proteção geral da API
  general: {
    windowMs: 60 * 1000, // 1 minuto
    maxRequests: 100,
  },

  // Proteção contra brute force de login
  login: {
    windowMs: 15 * 60 * 1000, // 15 minutos
    maxRequests: 5,
    message: 'Muitas tentativas de login. Tente novamente em 15 minutos.',
  },

  // Proteção contra brute force de signup
  signup: {
    windowMs: 60 * 60 * 1000, // 1 hora
    maxRequests: 3,
    message: 'Muitas tentativas de cadastro. Tente novamente em 1 hora.',
  },

  // Proteção para criação de agentes
  createAgent: {
    windowMs: 60 * 1000, // 1 minuto
    maxRequests: 10,
  },

  // Proteção para envio de mensagens
  sendMessage: {
    windowMs: 60 * 1000, // 1 minuto
    maxRequests: 50,
  },

  // Proteção para API pública
  publicAPI: {
    windowMs: 60 * 1000, // 1 minuto
    maxRequests: 30,
  },
};

/**
 * Factory para criar rate limiters
 */
export function createRateLimiter(config: RateLimitConfig): RateLimiter {
  return new RateLimiter(config);
}

/**
 * Criar múltiplos rate limiters para diferentes endpoints
 */
export function setupRateLimiters() {
  return {
    general: createRateLimiter(RateLimitConfigs.general),
    login: createRateLimiter(RateLimitConfigs.login),
    signup: createRateLimiter(RateLimitConfigs.signup),
    createAgent: createRateLimiter(RateLimitConfigs.createAgent),
    sendMessage: createRateLimiter(RateLimitConfigs.sendMessage),
    publicAPI: createRateLimiter(RateLimitConfigs.publicAPI),
  };
}

export default RateLimiter;
