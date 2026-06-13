import { File, Folder } from 'lucide-react';

interface FileExplorerProps {
  files: Record<string, any>;
  onFileSelect: (path: string) => void;
  selectedFile: string | null;
}

export function FileExplorer({ files, onFileSelect, selectedFile }: FileExplorerProps) {
  const renderTree = (nodes: any, path = '') => {
    return Object.entries(nodes).map(([name, node]: [string, any]) => {
      const currentPath = path ? `${path}/${name}` : name;
      const isFolder = 'directory' in node;

      return (
        <div key={currentPath} style={{ marginLeft: '12px' }}>
          <div
            onClick={() => !isFolder && onFileSelect(currentPath)}
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: isFolder ? 'default' : 'pointer',
              padding: '4px',
              backgroundColor: selectedFile === currentPath ? '#37373d' : 'transparent',
              borderRadius: '4px'
            }}
          >
            {isFolder ? <Folder size={16} style={{ marginRight: '6px' }} /> : <File size={16} style={{ marginRight: '6px' }} />}
            <span style={{ fontSize: '14px' }}>{name}</span>
          </div>
          {isFolder && renderTree(node.directory, currentPath)}
        </div>
      );
    });
  };

  return (
    <div style={{ padding: '8px', color: '#cccccc', backgroundColor: '#252526', height: '100%', overflowY: 'auto' }}>
      <h3 style={{ fontSize: '12px', textTransform: 'uppercase', marginBottom: '12px', paddingLeft: '8px' }}>Explorer</h3>
      {renderTree(files)}
    </div>
  );
}
