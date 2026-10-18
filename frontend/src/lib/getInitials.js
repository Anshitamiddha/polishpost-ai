// "Ada Lovelace" -> "AL", "ada" -> "A", missing name -> "".
export function getInitials(name) {
  return (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}
