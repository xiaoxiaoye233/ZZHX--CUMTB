export const filePickerPlugin = {
  install(app) {
    app.directive('open-file', {
      mounted(button, { value: inputId }) {
        button.onclick = () => button.ownerDocument.getElementById(inputId)?.click()
      },
      beforeUnmount(button) {
        button.onclick = null
      },
    })
  },
}
