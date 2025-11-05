import { Config, ViewTypeInfo, PreviewResponse } from "@/types";

const API_BASE_URL = "http://localhost:8000";

export class ApiClient {
  async getConfig(): Promise<Config> {
    const response = await fetch(`${API_BASE_URL}/api/config`);
    if (!response.ok) {
      throw new Error(`Failed to fetch config: ${response.statusText}`);
    }
    return response.json();
  }

  async saveConfig(config: Config): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Failed to save config: ${response.statusText}`);
    }
  }

  async getViewTypes(): Promise<ViewTypeInfo[]> {
    const response = await fetch(`${API_BASE_URL}/api/views`);
    if (!response.ok) {
      throw new Error(`Failed to fetch view types: ${response.statusText}`);
    }
    return response.json();
  }

  async generatePreview(
    viewType: string,
    params: Record<string, any>
  ): Promise<PreviewResponse> {
    const response = await fetch(`${API_BASE_URL}/api/preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        view_type: viewType,
        params,
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Failed to generate preview: ${response.statusText}`);
    }
    return response.json();
  }
}

export const apiClient = new ApiClient();
