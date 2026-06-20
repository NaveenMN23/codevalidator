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
      setIsOpen(!isOpen);
    } else {
      onSelect(path);
    }
  }, [isFolder, isOpen, onSelect, path]);

  const isSelected = selectedFile === path;

  return (
    <div className="select-none">
      <div
        onClick={handleClick}
        className={`flex items-center py-1 px-2 cursor-pointer transition-all duration-150 group ${
          isSelected ? 'text-primary border-r-2 border-primary font-bold' : 'hover:bg-black/[0.03] dark:hover:bg-white/[0.03] text-text-muted hover:text-text-main'
        }`}
        style={{ paddingLeft: `${depth * 10 + 6}px` }}
      >
        <div className="w-3.5 h-3.5 flex items-center justify-center mr-1 shrink-0">
          {isFolder ? (
            isOpen ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />
          ) : null}
        </div>
        <div className="mr-1.5 shrink-0">
          {isFolder ? (
            <Folder size={14} className={isOpen ? 'text-primary/60' : 'text-text-muted/60'} />
          ) : (
            <File size={14} className={isSelected ? 'text-primary' : 'text-text-muted/60 group-hover:text-text-muted'} />
          )}
        </div>
        <span className="text-[12px] truncate font-medium tracking-tight">{name}</span>
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
  return (
    <div className="h-full flex flex-col bg-background">
      <div className="px-3 py-2 border-b border-border-main flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-[0.15em] text-text-muted">Explorer</span>
      </div>
      <div className="flex-grow overflow-y-auto py-1 scrollbar-thin">
        {Object.entries(files || {}).length > 0 ? (
          Object.entries(files).sort(([a], [b]) => a.localeCompare(b)).map(([name, node]) => (
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
    </div>
  );
}
