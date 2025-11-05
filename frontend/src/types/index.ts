export interface Schedule {
  cron: string | null;
  type: string;
  params: Record<string, any> | null;
}

export interface Device {
  name: string;
  device_id: string;
  schedules: Schedule[] | null;
}

export interface Config {
  api_key: string;
  devices: Device[];
}

export interface ViewTypeInfo {
  name: string;
  params_schema: {
    properties: Record<string, any>;
    required?: string[];
    title?: string;
    type?: string;
  };
}

export interface PreviewResponse {
  image: string;
  filename: string;
}
