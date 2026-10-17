interface IconProps {
  src: string;
  size?: number; // видимый размер значка в px
  className?: string;
}

export default function Icon({ src, size = 20, className = "" }: IconProps) {
  return (
    <span
      aria-hidden
      className={`icon-mask ${className}`}
      style={{ width: size, height: size, ["--icon" as string]: `url(${src})` }}
    />
  );
}