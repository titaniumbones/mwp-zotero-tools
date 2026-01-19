;;; run-tests.el --- Test runner for zotero-elisp -*- lexical-binding: t; -*-

;;; Commentary:
;; Test runner script for zotero-elisp test suite.
;; Installs required packages if running in batch mode.

;;; Code:

(require 'package)

;; Initialize package system
(setq package-user-dir (expand-file-name "elpa-test" temporary-file-directory))
(package-initialize)

;; Add MELPA for request package
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)

;; Install request package if not available
(unless (package-installed-p 'request)
  (package-refresh-contents)
  (package-install 'request))

;; Add directories to load path
(add-to-list 'load-path (file-name-directory (or load-file-name buffer-file-name)))
(add-to-list 'load-path (expand-file-name ".." (file-name-directory (or load-file-name buffer-file-name))))
(add-to-list 'load-path (expand-file-name "fixtures" (file-name-directory (or load-file-name buffer-file-name))))

;; Load fixture loader
(require 'load-fixtures)

;; Load test files
(require 'test-org-zotero-client)
(require 'test-zotero-api)

;; Run all tests matching "test-" prefix
(ert-run-tests-batch-and-exit "^test-")

;;; run-tests.el ends here