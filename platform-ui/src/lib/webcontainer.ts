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

export async function runCommand(
  webcontainer: WebContainer, 
  command: string, 
  args: string[], 
  onData: (data: string) => void,
  terminal?: any
) {
  const process = await webcontainer.spawn(command, args);
  
  // Handle output
  process.output.pipeTo(new WritableStream({
    write(data) {
      onData(data);
    }
  }));

  // Handle input from terminal
  const input = process.input.getWriter();
  if (terminal) {
    const disposable = terminal.onData((data: string) => {
      input.write(data);
    });
    
    const exitCode = await process.exit;
    disposable.dispose();
    input.close();
    return exitCode;
  }

  const exitCode = await process.exit;
  input.close();
  return exitCode;
}
