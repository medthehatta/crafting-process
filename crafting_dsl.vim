" crafting_dsl.vim — Vim syntax file for the crafting-process recipe DSL
"
" DSL structure recap:
"   output(s) | process name: attr=val [anno=val | anno2=val2]
"   input(s)
"
"   @augment_name          ← augment block line
"   @aug1 @aug2            ← composed augments
"
"   foo = 2 bar            ← minimal inline form (no process name)
"   out | name: = inputs   ← inline inputs on header line
"   ---                    ← section separator

if exists("b:current_syntax")
  finish
endif


" ── Comments ────────────────────────────────────────────────────────────────

syn match craftingComment "#.*$" contains=@Spell


" ── Section separator ───────────────────────────────────────────────────────

syn match craftingSeparator "^---\s*$"


" ── Augment decorators: @name ───────────────────────────────────────────────
" Matches @token anywhere — standalone augment lines, inline in headers,
" or inside attribute lists.

syn match craftingAugment "@\w\+"


" ── Annotation blocks: [key=val | key2=val2] ────────────────────────────────
" Defined as a region so the pipe inside doesn't read as a process separator.
" Numbers, augment tokens, and contained annotation items are allowed inside.

syn region craftingAnnotation start="\[" end="\]" keepend contains=craftingAnnotationKey,craftingAnnotationVal,craftingAnnotationPipe,craftingNumber,craftingAugment

" key  in key=val (word immediately before =)
syn match craftingAnnotationKey "\w\+\ze\s*=" contained

" value in key=val (everything after = up to | or ])
syn match craftingAnnotationVal "=\s*\zs[^|=\]]\+" contained

" | separator inside annotation blocks
syn match craftingAnnotationPipe "|" contained


" ── Attribute keywords after the colon ──────────────────────────────────────
" Highlight known attribute names in the header's attribute section.
" Using a match with \ze so the = itself stays an operator.

syn match craftingAttrKeyword "\<duration\>\ze\s*="
syn match craftingAttrKeyword "\<mode\>\ze\s*="


" ── Quantities (numbers) ────────────────────────────────────────────────────
" Integers and decimals that appear as resource amounts.

syn match craftingNumber "\<\d\+\(\.\d\+\)\?\>"


" ── Operators and punctuation ───────────────────────────────────────────────

" Process separator pipe (outside annotation regions)
syn match craftingPipe "|"

" Colon introducing the attribute section
syn match craftingColon ":"

" = used as inline-input marker or attribute assignment
syn match craftingEquals "="

" + separating multiple outputs or multiple inputs
syn match craftingPlus "+"


" ── Highlight links ─────────────────────────────────────────────────────────

hi def link craftingComment       Comment
hi def link craftingSeparator     PreProc

hi def link craftingAugment       PreProc

hi def link craftingAnnotation    Special
hi def link craftingAnnotationKey Identifier
hi def link craftingAnnotationVal Constant
hi def link craftingAnnotationPipe Delimiter

hi def link craftingAttrKeyword   Keyword

hi def link craftingNumber        Number

hi def link craftingPipe          Operator
hi def link craftingColon         Operator
hi def link craftingEquals        Operator
hi def link craftingPlus          Operator


let b:current_syntax = "crafting_dsl"
