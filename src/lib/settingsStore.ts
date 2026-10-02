export interface MyraaSettings {
  autoStart: boolean;
  animations: boolean;
  wakeWordEnabled: boolean;
  wakePhrase: string;
  micDeviceId: string;
  sensitivity: number;
  themeColor: string;
}

export const DEFAULT_SETTINGS: MyraaSettings = {
  autoStart: false,
  animations: true,
  wakeWordEnabled: false,
  wakePhrase: "hey myraa",
  micDeviceId: "",
  sensitivity: 50,
  themeColor: "charcoal",
};

const STORAGE_KEY = "myraa_settings_v2";

export function loadSettings(): MyraaSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    }
  } catch {
    // Ignore storage errors
  }
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(patch: Partial<MyraaSettings>): MyraaSettings {
  const current = loadSettings();
  const next = { ...current, ...patch };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Ignore storage errors
  }
  return next;
}
