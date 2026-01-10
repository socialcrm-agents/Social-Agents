/**
 * WorkspaceSettings.tsx
 * Componente principal de configurações de workspace e domínios
 */

import React, { useState, useEffect } from 'react';
import { trpc } from '../utils/trpc';
import DomainManager from './DomainManager';
import BrandingSettings from './BrandingSettings';
import SecuritySettings from './SecuritySettings';

type TabType = 'general' | 'domains' | 'branding' | 'security' | 'integrations';

interface WorkspaceSettingsProps {
  workspaceId: number;
}

const WorkspaceSettings: React.FC<WorkspaceSettingsProps> = ({ workspaceId }) => {
  const [activeTab, setActiveTab] = useState<TabType>('general');
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  // Queries
  const { data: workspace, isLoading: workspaceLoading } = trpc.domain.getWorkspace.useQuery({
    workspaceId,
  });

  const { data: domains } = trpc.domain.listDomains.useQuery({
    workspaceId,
  });

  // Mutations
  const updateWorkspaceMutation = trpc.domain.updateWorkspace.useMutation({
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Workspace atualizado com sucesso',
      });
    },
    onError: (error) => {
      setNotification({
        type: 'error',
        message: error.message,
      });
    },
  });

  const updateSettingsMutation = trpc.domain.updateWorkspaceSettings.useMutation({
    onSuccess: () => {
      setNotification({
        type: 'success',
        message: 'Configurações atualizadas com sucesso',
      });
    },
    onError: (error) => {
      setNotification({
        type: 'error',
        message: error.message,
      });
    },
  });

  if (workspaceLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">Workspace não encontrado</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{workspace.name}</h1>
              <p className="text-gray-600 mt-1">Gerenciar configurações do workspace</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Plano: <span className="font-semibold">{workspace.plan}</span></p>
              <p className="text-sm text-gray-600">Domínios: <span className="font-semibold">{domains?.length || 0}</span></p>
            </div>
          </div>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div className={`max-w-7xl mx-auto px-4 py-4 mt-4 rounded-lg ${
          notification.type === 'success' ? 'bg-green-50 text-green-800' :
          notification.type === 'error' ? 'bg-red-50 text-red-800' :
          'bg-blue-50 text-blue-800'
        }`}>
          <p className="text-sm font-medium">{notification.message}</p>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-1">
            <nav className="space-y-1 bg-white rounded-lg shadow">
              {[
                { id: 'general', label: 'Geral', icon: '⚙️' },
                { id: 'domains', label: 'Domínios', icon: '🌐' },
                { id: 'branding', label: 'Branding', icon: '🎨' },
                { id: 'security', label: 'Segurança', icon: '🔒' },
                { id: 'integrations', label: 'Integrações', icon: '🔗' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-blue-50 text-blue-700 border-l-4 border-blue-500'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3">
            {activeTab === 'general' && (
              <GeneralSettings
                workspace={workspace}
                onUpdate={updateWorkspaceMutation.mutate}
                isLoading={updateWorkspaceMutation.isPending}
              />
            )}

            {activeTab === 'domains' && (
              <DomainManager
                workspaceId={workspaceId}
                domains={domains || []}
              />
            )}

            {activeTab === 'branding' && (
              <BrandingSettings
                workspaceId={workspaceId}
                settings={workspace.settings}
                onUpdate={updateSettingsMutation.mutate}
                isLoading={updateSettingsMutation.isPending}
              />
            )}

            {activeTab === 'security' && (
              <SecuritySettings
                workspaceId={workspaceId}
                settings={workspace.settings}
                onUpdate={updateSettingsMutation.mutate}
                isLoading={updateSettingsMutation.isPending}
              />
            )}

            {activeTab === 'integrations' && (
              <IntegrationsSettings
                workspaceId={workspaceId}
                settings={workspace.settings}
                onUpdate={updateSettingsMutation.mutate}
                isLoading={updateSettingsMutation.isPending}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// COMPONENTE: CONFIGURAÇÕES GERAIS
// ============================================================================

interface GeneralSettingsProps {
  workspace: any;
  onUpdate: (data: any) => void;
  isLoading: boolean;
}

const GeneralSettings: React.FC<GeneralSettingsProps> = ({ workspace, onUpdate, isLoading }) => {
  const [formData, setFormData] = useState({
    name: workspace.name,
    description: workspace.description || '',
    color: workspace.color || '#3B82F6',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({
      workspaceId: workspace.id,
      ...formData,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Configurações Gerais</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Nome */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Nome do Workspace
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Ex: Meu Negócio"
          />
        </div>

        {/* Descrição */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Descrição
          </label>
          <textarea
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Descreva seu workspace"
            rows={4}
          />
        </div>

        {/* Cor */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Cor Primária
          </label>
          <div className="flex items-center gap-4">
            <input
              type="color"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
              className="h-10 w-20 border border-gray-300 rounded cursor-pointer"
            />
            <input
              type="text"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="#3B82F6"
            />
          </div>
        </div>

        {/* Botão Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {isLoading ? 'Salvando...' : 'Salvar Alterações'}
          </button>
        </div>
      </form>
    </div>
  );
};

// ============================================================================
// COMPONENTE: CONFIGURAÇÕES DE INTEGRAÇÕES
// ============================================================================

interface IntegrationsSettingsProps {
  workspaceId: number;
  settings: any;
  onUpdate: (data: any) => void;
  isLoading: boolean;
}

const IntegrationsSettings: React.FC<IntegrationsSettingsProps> = ({
  workspaceId,
  settings,
  onUpdate,
  isLoading,
}) => {
  const [formData, setFormData] = useState({
    webhookUrl: settings?.webhookUrl || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({
      workspaceId,
      webhookUrl: formData.webhookUrl,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Integrações</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Webhook URL */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Webhook URL
          </label>
          <input
            type="url"
            value={formData.webhookUrl}
            onChange={(e) => setFormData({ ...formData, webhookUrl: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="https://seu-servidor.com/webhook"
          />
          <p className="text-sm text-gray-600 mt-2">
            Receberá notificações de eventos do workspace
          </p>
        </div>

        {/* Botão Submit */}
        <button
          type="submit"
          disabled={isLoading}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {isLoading ? 'Salvando...' : 'Salvar Alterações'}
        </button>
      </form>
    </div>
  );
};

export default WorkspaceSettings;
