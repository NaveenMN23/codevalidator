import { WebContainer } from '@webcontainer/api';

let webcontainerInstance: WebContainer | null = null;

export async function getWebContainer() {
  if (webcontainerInstance) return webcontainerInstance;
  webcontainerInstance = await WebContainer.boot();
  return webcontainerInstance;
}

export async function mountFiles(webcontainer: WebContainer, files: Record<string, any>) {
  await webcontainer.mount(files);
}

export async function runCommand(webcontainer: WebContainer, command: string, args: string[], onData: (data: string) => void) {
  const process = await webcontainer.spawn(command, args);
  process.output.pipeTo(new WritableStream({
    write(data) {
      onData(data);
    }
  }));
  return process.exit;
}
