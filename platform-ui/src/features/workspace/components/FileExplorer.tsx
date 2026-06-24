import { useCallback, useState } from 'react';
import { File, Folder, ChevronRight, ChevronDown } from 'lucide-react';

interface FileExplorerProps {
  files: Record<string, any>;
  onSelect: (path: string) => void;
  selectedFile: string | null;
}

interface TreeItemProps {
  name: string;
  node: any;
  path: string;
  onSelect: (path: string) => void;
  selectedFile: string | null;
  depth: number;
}

function TreeItem({ name, node, path, onSelect, selectedFile, depth }: TreeItemProps) {
  const isFolder = 'directory' in node;
  const [isOpen, setIsOpen] = useState(true);

  const handleClick = useCallback(() => {
    if (isFolder) {
      setIsOpen(v => !v);
    } else {
      onSelect(path);
    }
  }, [isFolder, isOpen, onSelect, path]);

  const isSelected = selectedFile === path;

  return (
    <div className="select-none">
      <div
        onClick={handleClick}
        className={`flex items-center py-[3px] cursor-pointer group ${
          isSelected
            ? 'bg-white/10 text-text-main'
            : 'text-text-muted hover:bg-white/[0.07] hover:text-text-main'
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <div className="w-4 h-4 flex items-center justify-center mr-0.5 shrink-0">
          {isFolder ? (
            isOpen
              ? <ChevronDown size={13} className="text-text-muted" />
              : <ChevronRight size={13} className="text-text-muted" />
          ) : null}
        </div>
        <div className="mr-1.5 shrink-0">
          {isFolder ? (
            <Folder size={14} className={isOpen ? 'text-[#dcb67a]' : 'text-[#c8a96e]'} />
          ) : (
            <File size={14} className={isSelected ? 'text-text-main' : 'text-[#858585] group-hover:text-text-muted'} />
          )}
        </div>
        <span className="text-[13px] truncate">{name}</span>
      </div>
      {isFolder && isOpen && Object.entries(node.directory).map(([childName, childNode]: [string, any]) => (
        <TreeItem
          key={`${path}/${childName}`}
          name={childName}
          node={childNode}
          path={`${path}/${childName}`}
          onSelect={onSelect}
          selectedFile={selectedFile}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

export function FileExplorer({ files, onSelect, selectedFile }: FileExplorerProps) {
  const [workspaceOpen, setWorkspaceOpen] = useState(true);

  return (
    <div className="h-full flex flex-col bg-panel overflow-hidden">
      {/* WORKSPACE collapsible root section */}
      <div
        onClick={() => setWorkspaceOpen(v => !v)}
        className="flex items-center gap-1 px-2 py-1.5 cursor-pointer hover:bg-white/5 shrink-0"
      >
        {workspaceOpen
          ? <ChevronDown size={12} className="text-text-muted shrink-0" />
          : <ChevronRight size={12} className="text-text-muted shrink-0" />
        }
        <span className="text-[11px] font-bold uppercase tracking-wider text-text-main">Workspace</span>
      </div>

      {workspaceOpen && (
        <div className="flex-grow overflow-y-auto scrollbar-thin">
          {Object.entries(files || {}).length > 0 ? (
            Object.entries(files)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([name, node]) => (
                <TreeItem
                  key={name}
                  name={name}
                  node={node}
                  path={name}
                  onSelect={onSelect}
                  selectedFile={selectedFile}
                  depth={0}
                />
              ))
          ) : (
            <div className="px-4 py-8 text-center">
              <p className="text-[10px] text-text-muted font-bold uppercase tracking-wider">No files loaded</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
