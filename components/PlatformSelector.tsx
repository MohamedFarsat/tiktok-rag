import { Checkbox } from "./ui/checkbox";
import type { PlatformKey } from "../lib/types";

const PLATFORM_LABELS: Record<PlatformKey, string> = {
  tiktok: "TikTok",
  youtube: "YouTube",
  instagram: "Instagram",
  facebook: "Facebook"
};

interface PlatformSelectorProps {
  selected: PlatformKey[];
  onChange: (platforms: PlatformKey[]) => void;
  showWarning: boolean;
}

export function PlatformSelector({
  selected,
  onChange,
  showWarning
}: PlatformSelectorProps) {
  const togglePlatform = (platform: PlatformKey) => {
    if (selected.includes(platform)) {
      onChange(selected.filter((item) => item !== platform));
      return;
    }

    onChange([...selected, platform]);
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap gap-4">
        {(Object.keys(PLATFORM_LABELS) as PlatformKey[]).map((platform) => (
          <label
            key={platform}
            className="flex items-center gap-2 rounded-full border border-line bg-white px-4 py-2 text-sm text-ink shadow-sm"
          >
            <Checkbox
              checked={selected.includes(platform)}
              onCheckedChange={() => togglePlatform(platform)}
              aria-label={PLATFORM_LABELS[platform]}
            />
            <span>{PLATFORM_LABELS[platform]}</span>
          </label>
        ))}
      </div>
      {showWarning ? (
        <p className="text-xs text-accent">
          Select at least one platform to submit the question.
        </p>
      ) : null}
    </section>
  );
}
