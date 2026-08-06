import Editor from '@monaco-editor/react';

export interface EditorYamlProps {
  content: string;
  selectedPath: string | null;
  onContentChange: (value: string | undefined) => void;
}

export function EditorYaml({
  content,
  selectedPath,
  onContentChange,
}: EditorYamlProps) {
  return (
    <div data-testid="editor-yaml" className="flex-1 min-w-0 min-h-0">
      {selectedPath || content.trim() ? (
        <Editor
          height="100%"
          language="yaml"
          theme="vs-dark"
          value={content}
          onChange={onContentChange}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            tabSize: 2,
          }}
        />
      ) : (
        <div data-testid="editor-yaml-empty" className="flex items-center justify-center h-full text-slate-500">
          Select a workflow file or press <kbd className="mx-1 px-1.5 py-0.5 bg-slate-700 rounded text-xs font-mono">Cmd+O</kbd> to open
        </div>
      )}
    </div>
  );
}
