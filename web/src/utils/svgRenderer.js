/**
 * SVG Chức năng công cụ kết xuất
 * sẽ Markdown trong ```svg Chuyển đổi khối mã hàng rào thành nội tuyến SVG HTML
 */

/**
 * sẽ Markdown trong chuỗi ```svg Chuyển đổi khối mã hàng rào thành nội tuyến SVG HTML
 *
 * Sử dụng thuật toán quét lũy tiến thay vì một thuật toán lớn thông thường，để tránh sự không khớp của dấu ngược trong hàng rào và nội dung lồng nhau。
 * SVG Nội dung sẽ được nén thành một dòng duy nhất，ngăn chặn markdown-it HTML Chặn phân tích cú pháp cắt ngắn nội dung do dòng trống。
 *
 * @param {string} markdown - nguyên bản Markdown chuỗi
 * @returns {string} chuỗi đã chuyển đổi，SVG Hàng rào đã được thay thế bằng <div class="svg-inline-render"><svg>...</svg></div>
 */
export function renderSvgBlocks(markdown) {
  const lines = markdown.split('\n')
  const output = []
  let i = 0

  while (i < lines.length) {
    const openMatch = lines[i].match(/^( {0,3})(`{3,}|~{3,})\s*(\S*)/)

    if (openMatch && openMatch[3].toLowerCase() === 'svg') {
      const indent = openMatch[1]
      const fenceChar = openMatch[2]
      const openLine = lines[i]
      const svgLines = []
      i++

      // Quét hàng rào kín
      let closed = false
      while (i < lines.length) {
        const closeMatch = lines[i].match(/^( {0,3})(`{3,}|~{3,})\s*$/)
        if (
          closeMatch &&
          closeMatch[1].length <= indent.length &&
          closeMatch[2][0] === fenceChar[0] &&
          closeMatch[2].length >= fenceChar.length
        ) {
          closed = true
          // nén SVG dưới dạng một dòng，ngăn chặn markdown-it HTML Khối cắt bớt phân tích cú pháp
          const singleLine = svgLines
            .join('')
            .replace(/>\s+</g, '><')
            .replace(/\s{2,}/g, ' ')
            .trim()
          const actionsHtml = [
            `<div class="svg-actions">`,
            `<button class="svg-action-btn svg-copy-btn" type="button">Sao chép SVG</button>`,
            `<button class="svg-action-btn svg-png-btn" type="button">Sao chép dưới dạng PNG</button>`,
            `</div>`
          ].join('')
          output.push(`<div class="svg-inline-render">${actionsHtml}${singleLine}</div>`)
          i++
          break
        }
        svgLines.push(lines[i])
        i++
      }

      if (!closed) {
        // hàng rào không đóng — giữ nguyên như vậy（Bảo mật truyền phát）
        output.push(openLine)
        output.push(...svgLines)
      }
    } else {
      output.push(lines[i])
      i++
    }
  }

  return output.join('\n')
}
