import { FolderOpen, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type EditorMode = 'visual' | 'yaml';

export interface EditorToolbarProps {
  selectedPath: string | null;
  isDirty: boolean;
  mode: EditorMode;
  isSaving: boolean;
  isRunning: boolean;
  hasContent: boolean;
  onOpenFiles: () => void;
  onSwitchToVisual: () => void;
  onSwitchToYaml: () => void;
  onSave: () => void;
  onRun: () => void;
  onOpenSettings?: () => void;
}

const AMBER = "#e8a020";
const BG = "#131315";
const BORDER = "#252528";
const S2 = "#1a1a1d";
const MUTED = "#80808a";
const TEXT = "#f0f0f0";

export function EditorToolbar({
  selectedPath,
  isDirty,
  mode,
  isSaving,
  isRunning,
  hasContent,
  onOpenFiles,
  onSwitchToVisual,
  onSwitchToYaml,
  onSave,
  onRun,
  onOpenSettings,
}: EditorToolbarProps) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "0 16px",
      height: 40,
      background: BG,
      borderBottom: `1px solid ${BORDER}`,
      flexShrink: 0,
    }}>
      {/* Open */}
      <button
        onClick={onOpenFiles}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          background: "none", border: "none", cursor: "pointer",
          color: MUTED, fontSize: 11, fontFamily: "inherit", padding: "4px 8px",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = TEXT)}
        onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = MUTED)}
      >
        <FolderOpen size={13} />
        Open
      </button>

      <span style={{
        fontSize: 11, color: TEXT, overflow: "hidden",
        textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300,
      }}>
        {selectedPath ?? (hasContent ? "(new workflow)" : "")}
      </span>

      {isDirty && (
        <span style={{ fontSize: 10, color: AMBER }}>unsaved</span>
      )}

      <div style={{ flex: 1 }} />

      {/* YAML / Visual toggle */}
      <div style={{
        display: "flex",
        border: `1px solid ${BORDER}`,
        overflow: "hidden",
      }}>
        <button
          onClick={onSwitchToYaml}
          aria-pressed={mode === "yaml"}
          style={{
            padding: "5px 12px", fontSize: 10, fontFamily: "inherit",
            cursor: "pointer", border: "none", letterSpacing: "0.06em",
            background: mode === "yaml" ? AMBER : "transparent",
            color: mode === "yaml" ? "#000" : MUTED,
            borderRight: `1px solid ${BORDER}`,
            transition: "all 0.1s",
          }}
        >
          YAML
        </button>
        <button
          onClick={onSwitchToVisual}
          aria-pressed={mode === "visual"}
          style={{
            padding: "5px 12px", fontSize: 10, fontFamily: "inherit",
            cursor: "pointer", border: "none", letterSpacing: "0.06em",
            background: mode === "visual" ? AMBER : "transparent",
            color: mode === "visual" ? "#000" : MUTED,
            transition: "all 0.1s",
          }}
        >
          Visual
        </button>
      </div>

      {onOpenSettings && (
        <button
          onClick={onOpenSettings}
          title="Workflow Settings"
          style={{
            background: "none", border: "none", cursor: "pointer",
            color: MUTED, padding: "4px", display: "flex", alignItems: "center",
          }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = TEXT)}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = MUTED)}
        >
          <Settings size={13} />
        </button>
      )}

      {/* Save */}
      <button
        onClick={onSave}
        disabled={(!selectedPath && !hasContent) || (!!selectedPath && !isDirty) || isSaving}
        style={{
          padding: "5px 14px", fontSize: 10, fontFamily: "inherit",
          cursor: "pointer", letterSpacing: "0.04em",
          background: "transparent", color: MUTED,
          border: `1px solid ${BORDER}`,
          opacity: ((!selectedPath && !hasContent) || (!!selectedPath && !isDirty) || isSaving) ? 0.4 : 1,
          transition: "all 0.1s",
        }}
        onMouseEnter={(e) => {
          const el = e.currentTarget as HTMLElement;
          if (!el.disabled) { el.style.color = TEXT; el.style.borderColor = "#333338"; }
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget as HTMLElement;
          if (!el.disabled) { el.style.color = MUTED; el.style.borderColor = BORDER; }
        }}
      >
        {isSaving ? "Saving…" : "Save"}
      </button>

      {/* Run */}
      <button
        onClick={onRun}
        disabled={!hasContent || isRunning}
        style={{
          padding: "5px 14px", fontSize: 10, fontFamily: "inherit",
          cursor: "pointer", letterSpacing: "0.04em",
          background: AMBER, color: "#000",
          border: `1px solid ${AMBER}`, fontWeight: 700,
          opacity: (!hasContent || isRunning) ? 0.5 : 1,
          transition: "all 0.1s",
        }}
      >
        {isRunning ? "Starting…" : "▸ Run"}
      </button>
    </div>
  );
}
