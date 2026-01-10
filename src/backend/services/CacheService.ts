/**
 * CacheService.ts
 * Serviço de cache com Redis para otimizar performance
 * - Cache de prompts construídos
 * - Cache de embeddings
 * - Cache de respostas frequentes
 * - TTL configurável
 */

import Redis from 'ioredis';

interface CacheConfig {
  host: string;
  port: number;
  password?: string;
  db: number;
  ttl: number; // segundos
}

export class CacheService {
  private redis: Redis;
  private defaultTTL: number;

  constructor(config: CacheConfig) {
    this.redis = new Redis({
      host: config.host,
      port: config.port,
      password: config.password,
      db: config.db,
      retryStrategy: (times: number) => {
        const delay = Math.min(times * 50, 2000);
        return delay;
      },
      maxRetriesPerRequest: null,
    });

    this.defaultTTL = config.ttl;

    this.redis.on('connect', () => {
      console.log('[CacheService] Conectado ao Redis');
    });

    this.redis.on('error', (error: Error) => {
      console.error('[CacheService] Erro de conexão:', error);
    });
  }

  /**
   * Obter valor do cache
   */
  async get<T = any>(key: string): Promise<T | null> {
    try {
      const value = await this.redis.get(key);
      if (!value) {
        return null;
      }

      try {
        return JSON.parse(value) as T;
      } catch {
        // Se não for JSON, retornar como string
        return value as any;
      }
    } catch (error) {
      console.error(`[CacheService] Erro ao obter ${key}:`, error);
      return null;
    }
  }

  /**
   * Salvar valor no cache
   */
  async set(key: string, value: any, ttl?: number): Promise<void> {
    try {
      const ttlSeconds = ttl || this.defaultTTL;
      const serialized = typeof value === 'string' ? value : JSON.stringify(value);

      if (ttlSeconds > 0) {
        await this.redis.setex(key, ttlSeconds, serialized);
      } else {
        await this.redis.set(key, serialized);
      }

      console.log(`[CacheService] Cache set: ${key} (TTL: ${ttlSeconds}s)`);
    } catch (error) {
      console.error(`[CacheService] Erro ao salvar ${key}:`, error);
    }
  }

  /**
   * Deletar valor do cache
   */
  async delete(key: string): Promise<void> {
    try {
      await this.redis.del(key);
      console.log(`[CacheService] Cache deleted: ${key}`);
    } catch (error) {
      console.error(`[CacheService] Erro ao deletar ${key}:`, error);
    }
  }

  /**
   * Invalidar todos os caches de um padrão
   */
  async invalidatePattern(pattern: string): Promise<number> {
    try {
      const keys = await this.redis.keys(pattern);
      if (keys.length === 0) {
        return 0;
      }

      await this.redis.del(...keys);
      console.log(`[CacheService] ${keys.length} caches invalidados para padrão: ${pattern}`);
      return keys.length;
    } catch (error) {
      console.error(`[CacheService] Erro ao invalidar padrão ${pattern}:`, error);
      return 0;
    }
  }

  /**
   * Cache de prompt construído
   * Key: prompt:{agentId}:{trainingIds}
   */
  async getCachedPrompt(agentId: number, trainingIds: string[]): Promise<string | null> {
    const key = `prompt:${agentId}:${trainingIds.sort().join(',')}`;
    return this.get<string>(key);
  }

  async setCachedPrompt(
    agentId: number,
    trainingIds: string[],
    prompt: string,
    ttl?: number
  ): Promise<void> {
    const key = `prompt:${agentId}:${trainingIds.sort().join(',')}`;
    await this.set(key, prompt, ttl || 3600); // 1 hora por padrão
  }

  /**
   * Invalidar cache de prompts de um agente
   */
  async invalidateAgentPromptCache(agentId: number): Promise<number> {
    return this.invalidatePattern(`prompt:${agentId}:*`);
  }

  /**
   * Cache de embeddings
   * Key: embedding:{text_hash}
   */
  async getCachedEmbedding(textHash: string): Promise<number[] | null> {
    const key = `embedding:${textHash}`;
    return this.get<number[]>(key);
  }

  async setCachedEmbedding(textHash: string, embedding: number[], ttl?: number): Promise<void> {
    const key = `embedding:${textHash}`;
    await this.set(key, embedding, ttl || 86400); // 24 horas por padrão
  }

  /**
   * Cache de respostas frequentes
   * Key: response:{agentId}:{messageHash}
   */
  async getCachedResponse(agentId: number, messageHash: string): Promise<string | null> {
    const key = `response:${agentId}:${messageHash}`;
    return this.get<string>(key);
  }

  async setCachedResponse(
    agentId: number,
    messageHash: string,
    response: string,
    ttl?: number
  ): Promise<void> {
    const key = `response:${agentId}:${messageHash}`;
    await this.set(key, response, ttl || 3600); // 1 hora por padrão
  }

  /**
   * Cache de dados de usuário
   * Key: user:{userId}
   */
  async getCachedUser(userId: number): Promise<any | null> {
    const key = `user:${userId}`;
    return this.get(key);
  }

  async setCachedUser(userId: number, userData: any, ttl?: number): Promise<void> {
    const key = `user:${userId}`;
    await this.set(key, userData, ttl || 1800); // 30 minutos por padrão
  }

  async invalidateUserCache(userId: number): Promise<void> {
    await this.delete(`user:${userId}`);
  }

  /**
   * Obter estatísticas do cache
   */
  async getStats(): Promise<{
    connectedClients: number;
    usedMemory: string;
    totalKeys: number;
    promptCaches: number;
    embeddingCaches: number;
    responseCaches: number;
  }> {
    try {
      const info = await this.redis.info('memory');
      const keys = await this.redis.keys('*');
      const promptKeys = await this.redis.keys('prompt:*');
      const embeddingKeys = await this.redis.keys('embedding:*');
      const responseKeys = await this.redis.keys('response:*');

      // Parse info
      const memoryMatch = info.match(/used_memory_human:([^\r\n]+)/);
      const usedMemory = memoryMatch ? memoryMatch[1] : 'unknown';

      return {
        connectedClients: keys.length,
        usedMemory,
        totalKeys: keys.length,
        promptCaches: promptKeys.length,
        embeddingCaches: embeddingKeys.length,
        responseCaches: responseKeys.length,
      };
    } catch (error) {
      console.error('[CacheService] Erro ao obter estatísticas:', error);
      return {
        connectedClients: 0,
        usedMemory: 'error',
        totalKeys: 0,
        promptCaches: 0,
        embeddingCaches: 0,
        responseCaches: 0,
      };
    }
  }

  /**
   * Limpar todo o cache
   */
  async flush(): Promise<void> {
    try {
      await this.redis.flushdb();
      console.log('[CacheService] Cache completamente limpo');
    } catch (error) {
      console.error('[CacheService] Erro ao limpar cache:', error);
    }
  }

  /**
   * Fechar conexão
   */
  async close(): Promise<void> {
    await this.redis.quit();
    console.log('[CacheService] Conexão fechada');
  }
}

/**
 * Factory para criar instância de CacheService
 */
export function createCacheService(config?: Partial<CacheConfig>): CacheService {
  const defaultConfig: CacheConfig = {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_DB || '0'),
    ttl: 3600, // 1 hora por padrão
  };

  return new CacheService({ ...defaultConfig, ...config });
}

export default CacheService;
