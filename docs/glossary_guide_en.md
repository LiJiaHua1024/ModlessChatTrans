## Glossary Feature Guide

**Introduction**

The "Glossary" feature allows you to create custom translation rules. This ensures that specific terms, common phrases,
or messages containing dynamic information (like player names) are translated exactly how you want. You can add, modify,
and delete these rules in the "Glossary" window.

**Opening the Glossary Window**

In the main interface, open this feature window via the path "More Settings" -> "Glossary".

**Interface Overview**

Once you open the "Glossary" window, you will see:

1. **Input Area:**
    * **Source Term:** Enter the original text pattern you want to match.
    * **Target Term:** Enter the corresponding translation result.
    * **Add/Update Term:** Use this button to add a new rule or save changes to an existing one.
2. **Glossary Rules List:** Displays all the rules you have defined. You can click on a rule in the list to select it,
   and the selected rule will automatically populate the input fields above.
3. **Action Buttons Area:**
    * **Delete Selected:** Deletes the rule currently selected in the list.
    * **Save Glossary and Close:** Saves all your changes and closes this window.

**How to Add and Use Translation Rules**

**1. Adding Exact Match Rules**

This is the simplest type of rule, used for directly replacing text that matches exactly.

* **Steps:**
    1. In the "**Source Term**" input field, enter the **exact** original text you want to replace (e.g., `gg`).
    2. In the "**Target Term**" input field, enter the translation you want to display (e.g., `good game`).
    3. Click the "**Add/Update Term**" button.
* **Effect:** When the program receives a message that is **exactly** "gg" (ignoring leading/trailing spaces), it will
  be translated to "good game".

**2. Handling Dynamic Content with Variables (`{{variable_name}}`)**

Use variables when the original message contains parts that can change (like usernames, item names, etc.).

* **Syntax:**
    * Use `{{variable_name}}` in the "**Source Term**" field to mark the dynamic part you want to match and capture.
    * Variable names can contain **letters, numbers, underscores (`_`), and hyphens (`-`)**.
    * Use the **same** `{{variable_name}}` in the "**Target Term**" field to insert the content captured earlier.
* **Steps & Examples:**
    * **Example 1: Player Join**
        1. Source Term: `{{player}} joined the game.`
        2. Target Term: `{{player}} has joined the game.`
        3. Click "Add/Update Term".

        * Effect: Input `"Alice joined the game."` will be translated to `"Alice has joined the game."`. The system
          automatically identifies that `player` corresponds to "Alice".
    * **Example 2: Multiple Variables & Transformation**
        1. Source Term: `{{actor}} gave {{item}} to {{receiver}}.`
        2. Target Term: `The item {{item}} was given to {{receiver}} by {{actor}}.` (Target structure differs from
           source)
        3. Click "Add/Update Term".

        * Effect: `"Bob gave an apple to Charlie."` -> `"The item an apple was given to Charlie by Bob."` (Demonstrates
          variable capture and reordering in the translation).
    * **Example 3: Variable Reordering or Discarding**
        1. Source Term: `[{{channel}}] {{user}}: {{message}}`
        2. Target Term: `{{user}} says: {{message}}` (The `channel` variable is discarded here)
        3. Click "Add/Update Term".

        * Effect: `"[Global] Eve: Hi!"` -> `"Eve says: Hi!"`
        * **Important:** All `{{variables}}` used in the "**Target Term**" **must** also exist in the corresponding "*
          *Source Term**".

**3. Handling Repeated Variables**

If you use the **same variable name** multiple times in the "**Source Term**" (e.g., `{{name}} ... {{name}}`), the text
in the original message corresponding to both these positions **must be identical** for the rule to match.

* **Example:**
    1. Source Term: `{{admin}} kicked {{admin}} from the server.`
    2. Target Term: `Admin {{admin}} kicked themselves from the server.`
    3. Click "Add/Update Term".

    * Effect:
        * `"Operator kicked Operator from the server."` -> Matches successfully, translated to
          `"Admin Operator kicked themselves from the server."`
        * `"Admin kicked User from the server."` -> Does **not match** this rule, because the first `{{admin}}`
          captures "Admin", and the second captures "User" (they are different).

**4. Advanced Tip: Using Regular Expressions to Restrict Variable Format (`{{variable_name:regex_pattern}}`)**

This feature allows you, within the "**Source Term**" field, to specify a precise pattern (format requirement) for a
variable, instead of just matching any text. It's useful when you need to ensure a variable is a number, a specific code
format, etc.

* **Syntax:** In the "**Source Term**" field, immediately follow the variable name with an **English colon (`:`)** and a
  regular expression pattern.
    * **Please note:** You must use the standard English colon `:`, not any other similar-looking character (like a
      full-width colon sometimes used in East Asian typography). Using the wrong character will prevent the rule from
      working as expected.
* **What is a Regular Expression?**
    * It's a special sequence of characters that defines a search pattern, mainly for use in pattern matching with
      strings.
    * If you are unfamiliar with regular expressions, you can ignore this advanced feature for now, or learn more from
      resources like:
        * **Python's Official `re` Module Documentation:
          ** [https://docs.python.org/3/library/re.html](https://docs.python.org/3/library/re.html)
        * (You can also find many tutorials online by searching "regex tutorial")
    * Simple examples:
        * `\d+` : Requires matching one or more digits.
        * `[a-zA-Z]+`: Requires matching one or more English letters.
* **Example: Ensuring Player ID is Numeric**
    1. Source Term: `Player {{player_id:\d+}} disconnected.` (**Note:** The English colon `:` after `player_id`)
    2. Target Term: `Player {{player_id}} has disconnected.`
    3. Click "Add/Update Term".

    * Effect:
        * `"Player 12345 disconnected."` -> Matches successfully (because "12345" fits `\d+`), translated to
          `"Player 12345 has disconnected."`
        * `"Player abc disconnected."` -> Does **not match** this rule (because "abc" does not fit `\d+`).

**Managing Existing Rules**

* **Viewing:** All rules are displayed in the "**Glossary Rules**" list in the format `"Source Term" → "Target Term"`.
* **Selecting & Deselecting:**
    * **Click** on any rule in the list to **select** it. The selected rule will be highlighted, the "Delete Selected"
      button will become enabled, and the rule's "Source Term" and "Target Term" will be **automatically filled** into
      the input fields above.
    * **Click** the currently selected rule again to **deselect** it. Upon deselection, the rule will no longer be
      highlighted, the "Delete Selected" button will become disabled.
* **Modifying:**
    1. Click the rule you want to modify; its content will automatically appear in the input fields above.
    2. Modify the "Source Term" or "Target Term" directly in the input fields.
    3. Click the "**Add/Update Term**" button.
        * If you **did not** change the "Source Term" in the input field, the system will only update the "Target Term"
          for this rule.
        * If you **did** change the "Source Term" in the input field, the system will attempt to **replace** the
          originally selected rule with the new "Source Term" and "Target Term" (effectively renaming the source term).
          If the new source term conflicts with another existing rule, you will be asked to confirm the overwrite.
* **Deleting:**
    1. Click the rule you want to delete.
    2. Click the "**Delete Selected**" button.
    3. The rule will be removed from the list.

**Saving Changes**

After you have finished adding, modifying, or deleting rules, **it is crucial** to click the "**Save Glossary and Close
**" button to save all your work and close the window. Otherwise, the changes you made in this session will be lost.