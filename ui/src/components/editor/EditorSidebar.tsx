import { CostEstimatePanel } from '@/components/CostEstimatePanel';
import { SaveAsModal } from '@/components/SaveAsModal';

export interface EditorSidebarProps {
  showCost: boolean;
  hasContent: boolean;
  yamlContent: string;
  showSaveAs: boolean;
  isSaving: boolean;
  saveAsInitialFilename?: string;
  onSaveAs: (path: string) => void;
  onCloseSaveAs: () => void;
}

/** Bottom / overlay panels: cost estimate + save-as modal. */
export function EditorSidebar({
  showCost,
  hasContent,
  yamlContent,
  showSaveAs,
  isSaving,
  saveAsInitialFilename,
  onSaveAs,
  onCloseSaveAs,
}: EditorSidebarProps) {
  return (
    <>
      {showCost && hasContent && <CostEstimatePanel yamlContent={yamlContent} />}
      {showSaveAs && (
        <SaveAsModal
          onSave={onSaveAs}
          onClose={onCloseSaveAs}
          isPending={isSaving}
          initialFilename={saveAsInitialFilename}
        />
      )}
    </>
  );
}
