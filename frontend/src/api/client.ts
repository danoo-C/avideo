// REST + WebSocket client for the avideo server (spec-web.md §12).

export interface VersionInfo {
  version: string;
}

export async function getVersion(): Promise<VersionInfo> {
  const response = await fetch("/api/version");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as VersionInfo;
}
