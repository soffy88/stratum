# A P1 SOURCE REGISTRATION — 利率史（第四版）

STATUS=REGISTERED
MODE=ONE_BOOK_ONLY

## BookSource

- title: 利率史（第四版）
- author: [美]悉尼·霍默 理查德·西勒
- edition: 第四版
- translator: 曹建海
- publisher: 中信出版社
- isbn: 9787508617497
- language: zh
- source_format: PDF

## SourceVersion

- version: PDF-v1
- file_hash: sha256(pilot-pdf-bytes)
- format: PDF
- page_count: 400
- storage_uri: s3://pilot/利率史-4th.pdf

## Checksum Policy

- same checksum cannot create ambiguous version
- file_hash is the version identity anchor
- duplicate registration returns existing version

## Scope

- Chapter 1 only: 古代时期的信贷（巴比伦/古希腊/古罗马）
- Target pages: 1-30
- Expected KU candidates: 20-50

SOURCE_REGISTRATION=PASS
