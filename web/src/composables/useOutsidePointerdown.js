import { onBeforeUnmount, onMounted, unref } from 'vue'

/**
 * Set openRef to false when pointerdown hits outside ignoreRefs.
 *
 * Used for lightweight overlays (e.g. custom panels) outside a-dropdown that need "click outside to close".
 * Triggers in capture phase to prevent being blocked by stopPropagation inside components.
 *
 * @param {import('vue').Ref<boolean>} openRef Ref controlling visibility
 * @param {Array<import('vue').Ref<HTMLElement | null>>} ignoreRefs Clicking inside these refs will not close
 */
export function useOutsidePointerdown(openRef, ignoreRefs = []) {
  const handler = (event) => {
    if (!unref(openRef)) return
    const path = event.composedPath()
    const isInside = ignoreRefs.some((ref) => unref(ref) && path.includes(unref(ref)))
    if (!isInside) {
      openRef.value = false
    }
  }

  onMounted(() => document.addEventListener('pointerdown', handler, true))
  onBeforeUnmount(() => document.removeEventListener('pointerdown', handler, true))
}
