import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { CollapsibleSection } from './CollapsibleSection';
import { getCaoProfiles } from '@/lib/api';

const CAO_PROVIDERS: { value: string; label: string }[] = [
  { value: 'claude_code', label: 'Claude Code' },
  { value: 'kiro_cli', label: 'Kiro CLI' },
  { value: 'q_cli', label: 'Q CLI' },
];

const OUTPUT_FORMATS = ['auto', 'json', 'text'] as const;

export function useCAOProfiles() {
  return useQuery<{ profiles: string[] }>({
    queryKey: ['cao-profiles'],
    queryFn: getCaoProfiles,
    retry: 1,
    staleTime: 30_000,
  });
}

export interface CaoNodePanelProps {
  agent: string;
  config: Record<string, unknown>;
  onAgentChange: (agent: string) => void;
  onConfigChange: (key: string, value: unknown) => void;
}

export function CaoNodePanel({ agent, config, onAgentChange, onConfigChange }: CaoNodePanelProps) {
  const { data, isError } = useCAOProfiles();
  const profiles = data?.profiles ?? [];
  const profileName = agent.replace('cao://', '');

  // Fallback text input when server unavailable
  const [manualProfile, setManualProfile] = useState(profileName);

  return (
    <>
      {/* Profile Section */}
      <CollapsibleSection title="Profile" defaultOpen>
        {isError ? (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-amber-400 text-[11px]">
              <AlertTriangle size={12} />
              <span>CAO server unavailable — enter profile name manually</span>
            </div>
            <Input
              value={manualProfile}
              onChange={(e) => {
                setManualProfile(e.target.value);
                onAgentChange(`cao://${e.target.value}`);
              }}
              placeholder="profile_name.md"
              className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        ) : (
          <div>
            <label className="text-slate-400 block mb-0.5">Agent Profile</label>
            <Select
              value={profileName}
              onValueChange={(v) => onAgentChange(`cao://${v}`)}
            >
              <SelectTrigger className="h-7 bg-slate-700 border-slate-600 text-slate-200">
                <SelectValue placeholder="Select profile..." />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((name) => (
                  <SelectItem key={name} value={name}>
                    {name}
                  </SelectItem>
                ))}
                {profiles.length === 0 && (
                  <SelectItem value="_empty" disabled>
                    No profiles found
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
        )}

        <div>
          <label className="text-slate-400 block mb-0.5">Provider</label>
          <Select
            value={(config.provider as string) || 'claude_code'}
            onValueChange={(v) => onConfigChange('provider', v)}
          >
            <SelectTrigger className="h-7 bg-slate-700 border-slate-600 text-slate-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CAO_PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CollapsibleSection>

      {/* Output Section */}
      <CollapsibleSection title="Output">
        <div>
          <label className="text-slate-400 block mb-0.5">Format</label>
          <Select
            value={(config.output_format as string) || 'auto'}
            onValueChange={(v) => onConfigChange('output_format', v)}
          >
            <SelectTrigger className="h-7 bg-slate-700 border-slate-600 text-slate-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OUTPUT_FORMATS.map((f) => (
                <SelectItem key={f} value={f}>{f}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {(config.output_format as string) === 'json' && (
          <div>
            <label className="text-slate-400 block mb-0.5">Output Field (JSONPath)</label>
            <Input
              value={(config.output_field as string) || ''}
              onChange={(e) => onConfigChange('output_field', e.target.value)}
              placeholder="$.result"
              className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </CollapsibleSection>

      {/* Advanced Section */}
      <CollapsibleSection title="Advanced">
        <div>
          <label className="text-slate-400 block mb-0.5">Timeout (minutes)</label>
          <Input
            type="number"
            min={1}
            max={120}
            value={(config.timeout_minutes as number) || 60}
            onChange={(e) => onConfigChange('timeout_minutes', parseInt(e.target.value) || 60)}
            className="h-7 bg-slate-700 border-slate-600 text-slate-200"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </CollapsibleSection>
    </>
  );
}
