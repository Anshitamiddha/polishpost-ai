// "152/500", turning amber near the limit. It is linked to its field with
// aria-describedby, so screen readers announce it when the field is focused.
function CharacterCounter({ id, length, max }) {
  const state = length >= max ? "full" : length >= max * 0.9 ? "near" : "ok";

  return (
    <span id={id} className="cg-counter" data-state={state}>
      {length}/{max}
    </span>
  );
}

export default CharacterCounter;
