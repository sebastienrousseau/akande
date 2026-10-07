# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT

Output .github/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 650
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "source .venv/bin/activate"
Enter
Type "clear"
Enter
Sleep 500ms
Show

Type "akande --help"
Sleep 500ms
Enter
Sleep 3s

Type "clear"
Sleep 200ms
Enter

Type "akande skill list"
Sleep 500ms
Enter
Sleep 3s

Type "clear"
Sleep 200ms
Enter

Type "akande mcp --help"
Sleep 500ms
Enter
Sleep 3s
