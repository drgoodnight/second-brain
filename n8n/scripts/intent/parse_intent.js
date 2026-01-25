/**
 * Parse_Intent - AI Response Parser
 * 
 * Workflow: SimpleX_SecondBrain_Router
 * Node: Parse_Intent
 * 
 * Purpose: Extracts intent classification from AI model response.
 *          Handles markdown-wrapped JSON (```json ... ```) from Ollama/Gemma.
 * 
 * Input: AI model response (various formats)
 * Output: intent, target, content, query, message, sender
 * 
 * Last updated: 2026-01-25
 */

const aiResponse = $input.first().json;
let intent = 'chat';
let target = null;
let content = null;
let query = null;

try {
  let responseText = '';
  
  // Get the AI response text - handle multiple possible structures
  if (aiResponse.output?.[0]?.content?.[0]?.text) {
    responseText = aiResponse.output[0].content[0].text;
  } else if (aiResponse.output?.content?.[0]?.text) {
    responseText = aiResponse.output.content[0].text;
  } else if (aiResponse.content) {
    // Direct content field (common with Ollama)
    responseText = aiResponse.content;
  } else if (aiResponse.text) {
    responseText = aiResponse.text;
  }
  
  responseText = responseText.trim();
  
  // Strip markdown code fences if present
  // Handles: ```json ... ``` or ``` ... ```
  const codeBlockMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (codeBlockMatch) {
    responseText = codeBlockMatch[1].trim();
  }
  
  // Try to parse as JSON
  if (responseText.startsWith('{')) {
    const parsed = JSON.parse(responseText);
    // Support both 'intent' (new) and 'category' (old) for backwards compatibility
    intent = (parsed.intent || parsed.category || 'chat').toLowerCase();
    target = parsed.target || null;
    content = parsed.content || null;
    query = parsed.query || null;
  } else {
    // Fallback: treat as plain category word
    intent = responseText.toLowerCase();
  }
  
} catch (e) {
  // Log error for debugging
  console.log('Parse error:', e.message);
  intent = 'chat';
}

// Get original message from Prepare_Input
const prepareInput = $('Prepare_Input').first().json;

return {
  json: {
    intent: intent,
    target: target,
    content: content,
    query: query,
    message: prepareInput.message,
    sender: prepareInput.sender
  }
};
