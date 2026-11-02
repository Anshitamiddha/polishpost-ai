// Small stroke icons for the create-post page. They take their colour from the
// surrounding text (currentColor), so CSS alone handles hover and disabled.

function Icon({ size = 20, children, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function ImageIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="8.5" cy="9" r="1.6" />
      <path d="m21 16-5-5-8 8" />
    </Icon>
  );
}

export function UploadCloudIcon(props) {
  return (
    <Icon {...props}>
      <path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 9.5a4 4 0 0 1-.5 8" />
      <path d="M12 12v8" />
      <path d="m8.5 15.5 3.5-3.5 3.5 3.5" />
    </Icon>
  );
}

export function LightbulbIcon(props) {
  return (
    <Icon {...props}>
      <path d="M9 18h6" />
      <path d="M10 21h4" />
      <path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z" />
    </Icon>
  );
}

export function VideoIcon(props) {
  return (
    <Icon {...props}>
      <rect x="2.5" y="6" width="13" height="12" rx="2.5" />
      <path d="m15.5 10.5 6-3v9l-6-3" />
    </Icon>
  );
}

export function SparklesIcon(props) {
  return (
    <Icon {...props}>
      <path d="M10 3.5 11.8 9l5.5 1.8L11.8 12.6 10 18l-1.8-5.4L2.7 10.8 8.2 9z" />
      <path d="M18.5 3v4" />
      <path d="M16.5 5h4" />
      <path d="M18 16v4" />
      <path d="M16 18h4" />
    </Icon>
  );
}

export function ListIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h10" />
    </Icon>
  );
}

export function HashIcon(props) {
  return (
    <Icon {...props}>
      <path d="M5 9h14" />
      <path d="M5 15h14" />
      <path d="m10 4-2 16" />
      <path d="m16 4-2 16" />
    </Icon>
  );
}

export function ArrowRightIcon(props) {
  return (
    <Icon {...props}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </Icon>
  );
}

export function CloseIcon(props) {
  return (
    <Icon {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6 6 18" />
    </Icon>
  );
}

export function WandIcon(props) {
  return (
    <Icon {...props}>
      <path d="m4 20 10-10" />
      <path d="m13 7 4 4" />
      <path d="M17 3v3" />
      <path d="M15.5 4.5h3" />
      <path d="M20 10v3" />
      <path d="M18.5 11.5h3" />
    </Icon>
  );
}

export function RefreshIcon(props) {
  return (
    <Icon {...props}>
      <path d="M20 12a8 8 0 0 1-14 5.3" />
      <path d="M4 12a8 8 0 0 1 14-5.3" />
      <path d="M18 3v4h-4" />
      <path d="M6 21v-4h4" />
    </Icon>
  );
}

export function PencilIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z" />
      <path d="m14.5 7.5 3 3" />
    </Icon>
  );
}

export function InfoIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 8h.01" />
    </Icon>
  );
}

export function CopyIcon(props) {
  return (
    <Icon {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2.5" />
      <path d="M5 15V6a2 2 0 0 1 2-2h9" />
    </Icon>
  );
}

export function CheckIcon(props) {
  return (
    <Icon {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Icon>
  );
}
