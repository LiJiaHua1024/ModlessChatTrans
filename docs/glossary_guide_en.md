## **Glossary Feature Guide**

**Introduction**

The "Glossary" feature allows you to create custom translation rules to ensure that specific terms, common phrases, or
structured messages containing dynamic information (like player names) will always be translated exactly as you wish.
This feature improves translation quality in two main ways:

1. **Keyword Injection (no variables):** For general chat messages, the system recognizes the specific terms you define
   and "guides" the Large Language Model (LLM) to use your specified translations, ensuring consistency and accuracy.
2. **Template Matching (with variables):** For fixed-format messages (such as system notifications), the system can
   precisely parse and translate them according to your predefined template.

**Accessing the Glossary**

In the program's main interface, click the "**Glossary**" icon on the left navigation bar to enter the glossary
management interface.

**Interface Overview**

The glossary management interface is divided into several main areas:

1. **Input Area:**
    * **Source term:** Enter the raw text pattern or keyword you wish to match.
    * **Target term:** Enter the corresponding translation.
2. **Action Buttons:**
    * **Add/Update term:** Add a new rule or save changes to an existing rule.
    * **Clear input:** Clear the contents of the "Source term" and "Target term" input boxes.
3. **Glossary Rule List:**
    * All rules you have defined are displayed as a list. You can click a rule in the list to select it.
4. **List Management Buttons:**
    * **Delete selected terms:** Deletes the selected rule from the list.
    * **Clear terms:** Deletes all glossary rules in the list.

**How to Add and Use Translation Rules**

The Glossary supports two core types of rules. **For most users, Type 1 will satisfy everyday needs.**

### **Type 1: Add Keywords to Guide LLM Translation (No Variables)**

This is the most common, simplest, and recommended rule type for most users. It tells the translation engine: "Whenever
you see this word or phrase in any message, please always translate it to my specified target."

* **Important Note:**  
  When keywords appear inside longer sentences (contextual injection), this feature requires an **AI (LLM) translation
  service**; if you use traditional translation engines (such as Google Translate or DeepL), partial keyword injection
  within sentences will NOT take effect. However, if an incoming message body **exactly equals** a Source term you
  defined (e.g., a standalone `"gg"`), the tool matches it locally and returns the Target term directly—so exact matches
  work with traditional engines as well and consume zero API calls.
* **How it Works:**  
  When a message is sent to an LLM for translation, the program first checks whether the message contains any of the "
  Source terms" you've defined here (**note: substring checks are case-sensitive**, so defining `gg` will not match
  uppercase `GG`—add both if needed; up to 50 matched terms are injected per message). If so, the program sends these
  terms and their translations to the LLM as mandatory instructions. This is not a simple text replacement; rather, it
  gives the LLM precise context, making the result more in line with your expectations.
* **How to Use:**
    1. Enter an individual word or phrase in the `Source term` input (e.g. `gg`).
    2. Enter its standard translation in the `Target term` input (e.g. `well played`).
    3. Click the `Add/Update term` button.
* **Effect:**
    * **Original Message:** "That was a fun match, gg"
    * **Translation process:** The program recognizes `gg` in the message. It instructs the LLM: "Please translate ‘That
      was a fun match, gg’, and make sure to translate ‘gg’ as ‘well played’."
    * **Final Output:** "That was a fun match, well played."

### **Type 2: Use Templates and Variables to Handle Dynamic Content (Advanced Feature)**

**This is for advanced users.** When you need to handle original messages with a fixed structure but variable parts (
like usernames, item names, etc.—common in system tips in games), you can use template-matching rules with variables.
**These rules only trigger when the entire message body (the chat content after stripping player name prefixes or channel
tags) exactly matches the template.** Once matched, substitution happens locally with **zero latency and zero API
calls**, and works regardless of whether you use AI or traditional translation services.

* **Syntax:**
    * Use `{{variable_name}}` in the `Source term` input to mark dynamic parts to capture.
    * Variable names may contain **letters, numbers, underscores (`_`), and hyphens (`-`)**.
    * Use the **same** `{{variable_name}}` in the `Target term` to insert the previously captured content.
* **Usage & Examples:**
    * **Example 1: Player Joined**
        1. Source term: `{{player}} joined the game.`
        2. Target term: `{{player}} has joined the game.`
        3. Click `Add/Update term`.

        * **Effect:** Input "Alice joined the game." will be directly translated to "Alice has joined the game."
    * **Example 2: Multiple Variables**
        1. Source term: `{{actor}} gave {{item}} to {{receiver}}.`
        2. Target term: `{{actor}} gave {{item}} to {{receiver}}.`

        * **Effect:** "Bob gave an apple to Charlie." → "Bob gave an apple to Charlie."
    * **Example 3: Variable Reordering or Discarding**
        1. Source term: `[{{channel}}] {{user}}: {{message}}`
        2. Target term: `{{user}} says: {{message}}` (the channel variable is discarded)

        * **Effect:** "[Global] Eve: Hi!" → "Eve says: Hi!"
        * **Important:** Every `{{variable}}` used in the `Target term` **must** also appear in the corresponding
          `Source term`.

**Advanced Template Matching Tips**

The following tips only apply to **Type 2 (template with variables)** rules.

**1. Handling Repeated Variables**

If a **variable name** appears more than once in `Source term` (e.g. `{{name}} ... {{name}}`), then the corresponding
pieces of text in the original message **must be exactly the same** for the rule to match.

* **Example:**
    1. Source term: `{{admin}} kicked {{admin}} from the server.`
    2. Target term: `Admin {{admin}} kicked themselves from the server.`

    * **Effect:**
        * "Operator kicked Operator from the server." → Matched, becomes "Admin Operator kicked themselves from the
          server."
        * "Admin kicked User from the server." → **Does not match** this rule, because the two `{{admin}}` capture
          different texts.

**2. Using Regular Expressions to Restrict Variable Format (`{{variable_name:regex}}`)**

This feature allows you to specify a strict match pattern for a variable, instead of capturing any text.

* **Syntax:** Add an **English colon (:)** and a regular expression pattern right after the variable name in
  `Source term`.
    * **Important:** Use the standard half-width English colon `:`, *not* a full-width colon `：`!
    * Standard regex constructs including character classes and curly-brace quantifiers (e.g., `{{code:\d{2,4}}}`) are
      supported without treating inner `}` characters as the end of the variable.
* **What is a regular expression?**
    * It's a special symbolic language for describing patterns of text. It lets you precisely match the text format you
      want.
    * If you are unfamiliar with regular expressions, you may skip this advanced feature, or learn from resources like:
        * **Python Official `re` documentation:**
          [https://docs.python.org/3/library/re.html](https://docs.python.org/3/library/re.html)
* **Example: Ensure Player ID is Numeric**
    1. Source term: `Player {{player_id:\d+}} disconnected.`
    2. Target term: `Player {{player_id}} has disconnected.`

    * **Effect:**
        * "Player 12345 disconnected." → matched, translates as "Player 12345 has disconnected."
        * "Player abc disconnected." → **does not match** this rule.

**Managing Existing Rules**

* **Selecting:** **Click** any rule in the list to **select** it. The selected rule's content will auto-populate the
  input fields above for easy modification.
* **Editing:**
    1. Click the rule you want to modify.
    2. Edit the `Source term` or `Target term` as desired.
    3. Click the `Add/Update term` button. The system will update the currently selected rule with the contents of the
       input fields.
* **Deleting:**
    1. Click the rule you want to delete.
    2. Click the `Delete selected terms` button.
* **Clearing:** Click the `Clear terms` button to delete all rules in the list.

**Important Note (Saving & Applying Changes):** Adding, updating, deleting, or clearing rules only updates the in-memory
list in the UI and **does not save automatically to the config file**. Go to the **Start** menu on the left and click
**Save configuration** or **Save configuration and start** to persist changes to disk; if translation is already running,
restart it from **Start** for the updated glossary to take effect (using **Start directly** applies changes only to that
session without saving to disk).