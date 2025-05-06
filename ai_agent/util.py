# -*- coding: utf-8 -*-
"""
Refactored module to invoke an AWS Bedrock Agent with improved efficiency,
error handling, and readability. Intended for import into other scripts.
"""

import boto3
import textwrap
import sys
from botocore.exceptions import ClientError, BotoCoreError

# --- Configuration ---

# Specify the AWS region where your Bedrock Agent is deployed.
# Ensure this matches the region used in your AWS configuration/credentials.
# You might want to make this configurable (e.g., via environment variables or function arguments)
# if the importing script needs flexibility.
REGION_NAME = 'us-east-1'

# --- Boto3 Client Initialization ---

# Initialize the Bedrock Agent Runtime client once when the module is loaded.
# This client will be reused across multiple calls to invoke_agent.
try:
    bedrock_agent_runtime = boto3.client(
        service_name='bedrock-agent-runtime',
        region_name=REGION_NAME
    )
# Handle potential errors during initial client creation gracefully.
except (ClientError, BotoCoreError) as e:
    print(f"ERROR: Failed to initialize Boto3 client for Bedrock Agent Runtime: {e}", file=sys.stderr)
    # Set client to None or raise an exception to signal failure to the importing script.
    bedrock_agent_runtime = None
    # Alternatively: raise ImportError(f"Failed to initialize Boto3 client: {e}") from e

# --- Helper Functions for Trace Processing ---

def _print_indented(text: str, width: int, indent: str = '  '):
    """Helper to print text with indentation and wrapping."""
    # Use textwrap for clean formatting within the specified width.
    print(textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent))

def _process_orchestration_trace(trace_details: dict, width: int):
    """Processes and prints the orchestration part of the trace for debugging."""
    # Safely access orchestration trace details using .get() to avoid KeyErrors.
    orch_trace = trace_details.get('orchestrationTrace', {})

    # Print Rationale/Thought Process if available.
    rationale = orch_trace.get('rationale', {}).get('text')
    if rationale:
        print("\nAgent's thought process:")
        _print_indented(rationale, width)

    # Print Invocation Input Details, adapting to different invocation types.
    inv_input = orch_trace.get('invocationInput', {})
    inv_type = inv_input.get('invocationType', 'N/A') # Default to N/A if type is missing.
    print(f"\nInvocation Input ({inv_type}):")

    # Handle specific invocation types for detailed output.
    if 'actionGroupInvocationInput' in inv_input:
        agi = inv_input.get('actionGroupInvocationInput', {})
        print(f"  Action Group: {agi.get('actionGroupName', 'N/A')}")
        print(f"  Function: {agi.get('function', 'N/A')}")
        params = agi.get('parameters', [])
        print("  Parameters:")
        if params:
            for param in params:
                print(f"    - Name: {param.get('name', 'N/A')}, Type: {param.get('type', 'N/A')}, Value: {param.get('value', 'N/A')}")
        else:
            print("    N/A")
    elif 'knowledgeBaseLookupInput' in inv_input:
         kbl = inv_input.get('knowledgeBaseLookupInput', {})
         print(f"  Knowledge Base ID: {kbl.get('knowledgeBaseId', 'N/A')}")
         print(f"  Query Text: {kbl.get('text', 'N/A')}")
    elif 'codeInterpreterInput' in inv_input:
         cii = inv_input.get('codeInterpreterInput', {})
         print(f"  Code: {cii.get('code', 'N/A')}")
         print(f"  Files: {cii.get('files', 'N/A')}")
    else:
         # Fallback for unknown or other invocation types.
         print(f"  Details: {inv_input}") # Print raw input if type is not specifically handled.

    # Print Observation Details, adapting to different observation types.
    obs = orch_trace.get('observation', {})
    obs_type = obs.get('type', 'N/A')
    print(f"\nObservation ({obs_type}):")

    # Handle specific observation types.
    if 'actionGroupInvocationOutput' in obs:
        agio = obs.get('actionGroupInvocationOutput', {})
        print(f"  Action Group Output: {agio.get('text', 'N/A')}")

    if 'knowledgeBaseLookupOutput' in obs:
        kblo = obs.get('knowledgeBaseLookupOutput', {})
        refs = kblo.get('retrievedReferences', [])
        print("  Knowledge Base Lookup Output:")
        if refs:
            for i, ref in enumerate(refs):
                content = ref.get('content', {}).get('text', 'N/A')
                location_info = ref.get('location', {})
                # Determine location type (S3 or potentially others in future)
                if 's3Location' in location_info:
                    location = location_info.get('s3Location', {}).get('uri', 'N/A')
                elif 'webLocation' in location_info: # Example for future-proofing
                    location = location_info.get('webLocation', {}).get('url', 'N/A')
                else:
                    location = 'N/A'
                score = ref.get('score', 'N/A') # Retrieve confidence score if available.
                print(f"    Reference {i+1} (Score: {score}, Location: {location}):")
                # Print a snippet of the content for brevity.
                _print_indented(f"{content[:150]}...", width, indent='      ')
        else:
            print("    No references found.")

    if 'codeInterpreterInvocationOutput' in obs:
         cio = obs.get('codeInterpreterInvocationOutput', {})
         print("  Code Interpreter Output:")
         # Show snippet of execution output.
         print(f"    Execution Output: {cio.get('executionOutput', 'N/A')[:150]}...")
         print(f"    Execution Error: {cio.get('executionError', 'N/A')}")
         print(f"    Execution Timeout: {cio.get('executionTimeout', 'N/A')}")

    if 'finalResponse' in obs:
         # Check if final response text exists within the trace observation.
         final_response = obs.get('finalResponse', {}).get('text', '')
         # Only print if there's actual text, avoids printing empty "Final response" lines.
         if final_response:
            print(f"\nFinal response (from trace):")
            _print_indented(final_response, width)

    # Placeholder for other observation types (e.g., RepromptResponse) if needed in the future.

def _process_guardrail_trace(trace_details: dict, width: int):
    """Processes and prints the guardrail part of the trace for debugging."""
    # Safely access guardrail trace details.
    guard_trace = trace_details.get('guardrailTrace', {})
    action = guard_trace.get('action', 'N/A') # Guardrail action (e.g., INTERVENED, NONE).
    print(f"\nGuardrail Trace (Action: {action}):")

    # Combine input and output assessments for unified processing loop.
    assessments = guard_trace.get('inputAssessments', []) + guard_trace.get('outputAssessments', [])

    if not assessments:
        print("  No guardrail assessments found.")
        return # Exit early if no assessments to process.

    # Iterate through each assessment (could be multiple types per assessment).
    for assessment in assessments:
        # Process Content Policy results if present.
        if 'contentPolicy' in assessment:
            cp = assessment['contentPolicy']
            print("  Content Policy Assessment:")
            filters = cp.get('filters', [])
            if filters:
                for f in filters:
                    print(f"    - Filter: {f.get('type', 'N/A')} (Confidence: {f.get('confidence', 'N/A')}, Action: {f.get('action', 'N/A')})")
            else:
                print("    No content filters applied.")

        # Process Sensitive Information Policy results if present.
        if 'sensitiveInformationPolicy' in assessment:
            sip = assessment['sensitiveInformationPolicy']
            print("  Sensitive Information Policy Assessment:")
            pii_entities = sip.get('piiEntities', [])
            if pii_entities:
                 for pii in pii_entities:
                    print(f"    - PII Detected: {pii.get('type', 'N/A')} (Action: {pii.get('action', 'N/A')})")
            else:
                print("    No PII detected.")

        # Process Word Policy results if present.
        if 'wordPolicy' in assessment:
             wp = assessment['wordPolicy']
             print("  Word Policy Assessment:")
             # Check for matches in both custom and managed word lists.
             custom_matches = wp.get('customWords', [])
             managed_matches = wp.get('managedWordLists', [])
             if custom_matches or managed_matches:
                 for match in custom_matches:
                     print(f"    - Custom Word Match: {match.get('match', 'N/A')} (Action: {match.get('action', 'N/A')})")
                 for match in managed_matches:
                     print(f"    - Managed Word List Match: {match.get('match', 'N/A')} (Action: {match.get('action', 'N/A')})")
             else:
                 print("    No word policy matches.")

        # Placeholder: Add processing for 'topicPolicy' if Guardrails for Topics is used.

# --- Main Agent Invocation Function ---

def invoke_agent(agentId: str,
                 agentAliasId: str,
                 inputText: str,
                 sessionId: str,
                 enableTrace: bool = False,
                 endSession: bool = False,
                 width: int = 90):
    """
    Invokes the specified Bedrock Agent and handles the streaming response.

    Requires the 'bedrock_agent_runtime' client to be initialized globally
    in the module scope. Checks if the client initialization was successful.

    Args:
        agentId: The unique identifier of the Bedrock Agent.
        agentAliasId: The alias identifier for the Bedrock Agent version (e.g., TSTALIASID).
        inputText: The input text query for the agent.
        sessionId: The identifier for the current user session. Should persist across turns
                   in a conversation.
        enableTrace: If True, prints detailed trace information (rationale, function calls, etc.)
                     to standard output during processing. Useful for debugging.
                     If False (default), only prints the agent's final response chunks
                     as they arrive (streaming).
        endSession: If True, signals to the agent that this is the last interaction
                    in the current session. Defaults to False.
        width: The maximum width for wrapping printed text output (user input and trace details).

    Returns:
        A dictionary containing:
        - 'sessionId': The session ID used for the interaction (same as input).
        - 'agentResponse': A string containing the complete text response aggregated from the agent.
        - 'error': An error message string if an AWS API call or other exception occurred
                   during the invocation, otherwise None.

    Raises:
        Prints error messages to stderr for AWS API call failures or unexpected errors.
        May implicitly raise exceptions related to Boto3/AWS interaction if not caught.
    """
    # Check if the global client was initialized successfully.
    if bedrock_agent_runtime is None:
        error_message = "ERROR: Bedrock Agent Runtime client is not initialized. Cannot invoke agent."
        print(error_message, file=sys.stderr)
        return {
            'sessionId': sessionId,
            'agentResponse': "",
            'error': error_message
        }

    agent_response = ""
    final_session_id = sessionId # Use provided session ID; API doesn't change it here.
    error_message = None

    try:
        # --- User Input Display ---
        # Provides clear demarcation in the output log.
        print(f"\n{'='*width}")
        print(f"User Input (Session: {sessionId}):")
        _print_indented(inputText, width)
        print(f"{'-'*width}")
        print("Agent Output:")
        # Start agent output on the same line for a more natural chat flow if not tracing.
        if not enableTrace:
            print(" ", end="", flush=True)

        # --- API Call ---
        # Invoke the agent via the Boto3 client.
        response = bedrock_agent_runtime.invoke_agent(
            agentId=agentId,
            agentAliasId=agentAliasId,
            sessionId=sessionId,
            inputText=inputText,
            endSession=endSession,
            enableTrace=enableTrace
        )

        # --- Response Stream Processing ---
        event_stream = response.get("completion", [])
        for event in event_stream:
            # Handle 'chunk': Contains parts of the agent's response text.
            if 'chunk' in event:
                chunk = event['chunk']
                # Decode bytes safely, replacing errors if any occur.
                chunk_text = chunk.get('bytes', b'').decode('utf-8', errors='replace')
                # Aggregate the response text.
                agent_response += chunk_text
                # Print chunks immediately only if trace is disabled, for streaming effect.
                if not enableTrace and chunk_text:
                    # Replace newlines to prevent messing up indentation when streaming inline.
                    print(chunk_text.replace("\n", f"\n "), end="", flush=True)

            # Handle 'trace': Contains detailed execution steps (if enableTrace=True).
            elif 'trace' in event and enableTrace:
                trace = event.get('trace', {})
                # Handle potential variations in trace structure across SDK versions.
                trace_details = trace.get('trace', {})
                if not trace_details and isinstance(trace, dict) :
                     trace_details = trace # Adapt if trace details are not nested under 'trace'.

                # Delegate processing to helper functions for modularity.
                if 'orchestrationTrace' in trace_details:
                     _process_orchestration_trace(trace_details, width)
                if 'guardrailTrace' in trace_details:
                    _process_guardrail_trace(trace_details, width)
                # Add calls to process other trace types ('postProcessingTrace', etc.) if needed.

            # Note: Session ID doesn't typically change mid-stream or come from response headers
            # in the InvokeAgent API response body itself for streaming. Sticking to input sessionId.

    # --- Error Handling ---
    except ClientError as e:
        # Catch specific Boto3 client errors (API errors, validation errors).
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', 'No details provided')
        error_message = f"ERROR: AWS API Call Error: {error_code}: {error_msg}"
        print(f"\n{error_message}", file=sys.stderr)
    except BotoCoreError as e:
        # Catch general Boto3 core errors (e.g., credential issues).
        error_message = f"ERROR: BotoCore Error: {e}"
        print(f"\n{error_message}", file=sys.stderr)
    except Exception as e:
        # Catch any other unexpected Python errors during processing.
        error_message = f"ERROR: An unexpected error occurred: {e}"
        print(f"\n{error_message}", file=sys.stderr)
        # Consider adding full traceback logging here for easier debugging in complex scenarios
        # import traceback
        # traceback.print_exc()

    # --- Final Output & Return ---
    finally:
        # Ensure a newline follows the agent's output, regardless of tracing or streaming.
        print("\n")
        # If tracing was enabled, the chunks weren't printed live.
        # Print the final aggregated response now for completeness, after all trace details.
        if enableTrace and agent_response:
             print(f"{'-'*width}")
             print("Aggregated Agent Response:")
             _print_indented(agent_response, width)

        # Print a final separator and status summary.
        print(f"{'='*width}")
        print(f"Session ID: {final_session_id}")
        status = "Failed" if error_message else "Completed"
        print(f"Status: {status}")
        print(f"{'='*width}\n")

    # Return the collected data.
    return {
        'sessionId': final_session_id,
        'agentResponse': agent_response,
        'error': error_message # Will be None if no error occurred.
    }

# --- End of Module ---
# No example usage block (__name__ == "__main__") included.
# This file can now be imported using 'import your_module_name'.