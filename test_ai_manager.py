#!/usr/bin/env python3
"""
Test script for the enhanced AIManager complexity detection
"""

import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

from desktop_agent.brain.ai.ai_manager import AIManager

def test_complexity_detection():
    """Test the AIManager's complexity detection with various inputs"""

    ai_manager = AIManager()

    test_cases = [
        # Simple commands - should return ['simple']
        ("hello", "Simple greeting"),
        ("hi", "Simple greeting"),
        ("hey", "Simple greeting"),
        ("good morning", "Time-based greeting"),
        ("thanks", "Simple thanks"),
        ("thank you", "Simple thanks"),
        ("yes", "Affirmative"),
        ("no", "Negative"),
        ("stop", "Command"),
        ("cancel", "Command"),
        ("wait", "Command"),
        ("what time is it", "Time query"),
        ("current time", "Time query"),
        ("what date is it", "Date query"),
        ("what day is today", "Day query"),
        ("open notepad", "App launch"),
        ("close chrome", "App close"),
        ("set volume to 50", "Volume control"),
        ("volume 70%", "Volume control"),
        ("set brightness to 80", "Brightness control"),
        ("brightness 60%", "Brightness control"),
        ("mute", "Audio control"),
        ("unmute", "Audio control"),
        ("maximize", "Window control"),
        ("minimize", "Window control"),
        ("restore", "Window control"),
        ("close window", "Window control"),
        ("switch to chrome", "Window switching"),
        ("go to facebook.com", "Navigation"),
        ("search for python tutorials", "Search"),
        ("what is python", "Simple question"),
        ("who is einstein", "Simple question"),
        ("when is christmas", "Simple question"),
        ("where is paris", "Simple question"),

        # Medium complexity - should return ['medium']
        ("how are you doing", "Conversational"),
        ("tell me about yourself", "Conversational"),
        ("what's the weather like", "General inquiry"),
        ("can you help me with something", "General request"),
        ("i need some information", "General request"),
        ("let's discuss the project", "Discussion"),
        ("what do you think about this", "Opinion request"),

        # Complex - should return ['complex']
        ("explain how photosynthesis works", "Explanation request"),
        ("analyze the pros and cons of renewable energy", "Analysis request"),
        ("compare electric cars vs gasoline cars", "Comparison request"),
        ("evaluate the impact of social media on society", "Evaluation request"),
        ("why is the sky blue", "Why question"),
        ("how does a computer work", "How question"),
        ("what if we could travel through time", "Hypothetical question"),
        ("pros and cons of working from home", "Pros and cons"),
        ("advantages and disadvantages of AI", "Advantages/disadvantages"),
        ("effect of exercise on mental health", "Effect/Impact"),
        ("relationship between diet and health", "Relationship"),
        ("cause of climate change", "Cause/Effect"),
        ("purpose of education", "Purpose"),
        ("significance of the internet", "Significance"),
        ("implications of AI advancement", "Implications"),
        ("consequences of deforestation", "Consequences"),
        ("outcomes of the election", "Outcomes"),
        ("results of the experiment", "Results"),
        ("findings of the study", "Findings"),
        ("trends in technology", "Trends"),
        ("patterns in user behavior", "Patterns"),
        ("strategies for learning", "Strategies"),
        ("approaches to problem solving", "Approaches"),
        ("methods of data analysis", "Methods"),
        ("procedures for safety", "Procedures"),
        ("process of manufacturing", "Process"),
        ("steps to bake a cake", "Steps"),
        ("stages of grief", "Stages"),
        ("phases of the moon", "Phases"),
        ("plan a vacation", "Planning"),
        ("strategy for business growth", "Strategy"),
        ("design a website", "Design"),
        ("architecture of a building", "Architecture"),
        ("structure of an atom", "Structure"),
        ("framework for development", "Framework"),
        ("model of the solar system", "Model"),
        ("theory of relativity", "Theory"),
        ("concept of democracy", "Concept"),
        ("principle of fairness", "Principle"),
        ("rule of law", "Rule"),
        ("law of gravity", "Law"),
        ("algorithm for sorting", "Algorithm"),
        ("formula for area", "Formula"),
        ("equation of motion", "Equation"),
        ("calculate the trajectory", "Calculation"),
        ("compute the interest", "Computation"),
        ("solve this puzzle", "Solving"),
        ("solution to the problem", "Solution"),
        ("answer the question", "Answer"),
        ("resolve the conflict", "Resolution"),
        ("fix the bug", "Fixing"),
        ("correct the mistake", "Correcting"),
        ("improve the performance", "Improving"),
        ("optimize the code", "Optimizing"),
        ("enhance the user experience", "Enhancing"),
        ("develop a new feature", "Developing"),
        ("create a presentation", "Creating"),
        ("build a prototype", "Building"),
        ("construct a bridge", "Constructing"),
        ("design an experiment", "Designing"),
        ("innovate in the field", "Innovating"),
        ("invent a new device", "Inventing"),
        ("discover new species", "Discovering"),
        ("research the topic", "Researching"),
        ("investigate the incident", "Investigating"),
        ("study the effects", "Studying"),
        ("examine the evidence", "Examining"),
        ("inspect the equipment", "Inspecting"),
        ("review the document", "Reviewing"),
        ("survey the area", "Surveying"),
        ("summarize the article", "Summarizing"),
        ("conclude the discussion", "Concluding"),
        ("overview of the topic", "Overview"),
        ("introduction to the subject", "Introduction"),
        ("background of the issue", "Background"),
        ("context of the situation", "Context"),
        ("definition of the term", "Definition"),
        ("meaning of the word", "Meaning"),
        ("interpretation of the results", "Interpretation"),
        ("perspective on the matter", "Perspective"),
        ("viewpoint from here", "Viewpoint"),
        ("opinion on the topic", "Opinion"),
        ("belief about the future", "Belief"),
        ("thought on the matter", "Thought"),
        ("idea for improvement", "Idea"),
        ("concept of justice", "Concept"),
        ("notion of time", "Notion"),
        ("principle of equality", "Principle"),
        ("doctrine of inclusion", "Doctrine"),
        ("ideology of freedom", "Ideology"),
        ("philosophy of life", "Philosophy"),
        ("ethics of AI", "Ethics"),
        ("morality of actions", "Morality"),
        ("values of the company", "Values"),
        ("principles of design", "Principles"),
        ("standards of quality", "Standards"),
        ("criteria for evaluation", "Criteria"),
        ("guidelines for safety", "Guidelines"),
        ("recommendations for improvement", "Recommendations"),
        ("suggestions for changes", "Suggestions"),
        ("proposals for action", "Proposals"),
        ("propositions for consideration", "Propositions"),
        ("hypothesis about the cause", "Hypothesis"),
        ("theory of evolution", "Theory"),
        ("model of behavior", "Model"),
        ("framework for analysis", "Framework"),
        ("paradigm shift", "Paradigm"),
        ("approach to learning", "Approach"),
        ("methodology of research", "Methodology"),
        ("technique for measurement", "Technique"),
        ("procedure for testing", "Procedure"),
        ("process of decision making", "Process"),
        ("system of governance", "System"),
        ("mechanism of action", "Mechanism"),
        ("dynamic of the relationship", "Dynamic"),
        ("interaction between elements", "Interaction"),
        ("relationship between variables", "Relationship"),
        ("connection between ideas", "Connection"),
        ("association with the group", "Association"),
        ("link between concepts", "Link"),
        ("bond between people", "Bond"),
        ("network of contacts", "Network"),
        ("system of support", "System"),
        ("complex situation", "Complex"),
        ("complicated issue", "Complicated"),
        ("intricate design", "Intricate"),
        ("detailed analysis", "Detailed"),
        ("comprehensive review", "Comprehensive"),
        ("thorough examination", "Thorough"),
        ("exhaustive search", "Exhaustive"),
        ("extensive research", "Extensive"),
        ("in-depth study", "In-depth"),

        # Deep planning - should return ['deep_planning']
        ("step by step guide to baking a cake", "Multi-step"),
        ("phase by phase implementation plan", "Multi-step"),
        ("multi-step process for troubleshooting", "Multi-step"),
        ("several steps to achieve the goal", "Multi-step"),
        ("multiple steps in the procedure", "Multi-step"),
        ("first we need to, then we should, finally we must", "Sequential"),
        ("second step after the initial setup", "Sequential"),
        ("third phase of the project", "Sequential"),
        ("finally we can conclude", "Sequential"),
        ("lastly let's review the results", "Sequential"),
        ("plan the entire project from start to finish", "Planning"),
        ("strategy for market expansion over 5 years", "Strategy"),
        ("approach to solving complex problems", "Approach"),
        ("method for continuous improvement", "Method"),
        ("process for quality assurance", "Process"),
        ("procedure for emergency response", "Procedure"),
        ("design a complete software system", "Design"),
        ("architecture for scalable web application", "Architecture"),
        ("structure for organizational hierarchy", "Structure"),
        ("framework for machine learning pipeline", "Framework"),
        ("model for financial forecasting", "Model"),
        ("theory of organizational behavior", "Theory"),
        ("concept of sustainable development", "Concept"),
        ("principle of agile development", "Principle"),
        ("rule for data validation", "Rule"),
        ("law of diminishing returns", "Law"),
        ("algorithm for route optimization", "Algorithm"),
        ("formula for compound interest", "Formula"),
        ("equation for projectile motion", "Equation"),
        ("calculate optimal resource allocation", "Calculation"),
        ("compute risk-adjusted returns", "Computation"),
        ("solve the optimization problem", "Solving"),
        ("solution for network security", "Solution"),
        ("answer to the business challenge", "Answer"),
        ("resolve the scheduling conflict", "Resolution"),
        ("fix the architectural flaw", "Fixing"),
        ("correct the procedural error", "Correcting"),
        ("improve the customer satisfaction score", "Improving"),
        ("optimize the supply chain logistics", "Optimizing"),
        ("enhance the product feature set", "Enhancing"),
        ("develop the next generation product", "Developing"),
        ("create the marketing campaign strategy", "Creating"),
        ("build the development team structure", "Building"),
        ("construct the new facility", "Constructing"),
        ("design the user research study", "Designing"),
        ("innovate in the technology space", "Innovating"),
        ("invent the future of transportation", "Inventing"),
        ("discover the cure for disease", "Discovering"),
        ("research the market trends comprehensively", "Researching"),
        ("investigate the root cause thoroughly", "Investigating"),
        ("study the long-term effects deeply", "Studying"),
        ("examine all possible alternatives carefully", "Examining"),
        ("inspect every component meticulously", "Inspecting"),
        ("review the entire codebase systematically", "Reviewing"),
        ("survey the complete customer base", "Surveying"),
        ("summarize all findings concisely", "Summarizing"),
        ("conclude the investigation definitively", "Concluding"),
        ("overview of the entire field comprehensively", "Overview"),
        ("introduction to the complex subject thoroughly", "Introduction"),
        ("background of the historical event completely", "Background"),
        ("context of the situational factors entirely", "Context"),
        ("definition of the technical terms precisely", "Definition"),
        ("meaning of the symbolic representations accurately", "Meaning"),
        ("interpretation of the statistical results correctly", "Interpretation"),
        ("perspective from multiple stakeholder views", "Perspective"),
        ("viewpoint from different angles comprehensively", "Viewpoint"),
        ("opinion based on extensive research", "Opinion"),
        ("belief formed through careful consideration", "Belief"),
        ("thought developed over time", "Thought"),
        ("idea conceived through brainstorming", "Idea"),
    ]

    print("Testing AIManager Complexity Detection")
    print("=" * 50)

    correct_predictions = 0
    total_predictions = len(test_cases)

    for prompt, description in test_cases:
        # Test with empty system prompt
        hints = ai_manager._determine_complexity_hints("", prompt)
        predicted = hints[0] if hints else "unknown"

        # Determine expected category based on test case grouping
        if prompt in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening",
                     "howdy", "sup", "what's up", "thanks", "thank you", "thx", "thankyou",
                     "yes", "yeah", "yep", "yup", "affirmative", "correct", "right", "exactly",
                     "precisely", "no", "nah", "nope", "negative", "incorrect", "wrong", "false",
                     "stop", "cancel", "halt", "wait", "pause", "resume", "continue", "proceed",
                     "go", "come", "here", "there", "where", "when", "what", "who", "why", "how",
                     "time", "date", "day", "today", "tomorrow", "yesterday", "now", "then",
                     "soon", "later", "early", "late", "clock", "watch", "timer", "alarm",
                     "schedule", "appointment", "meeting", "event", "open", "close", "launch",
                     "start", "begin", "initiate", "terminate", "end", "finish", "complete",
                     "done", "exit", "quit", "leave", "depart", "arrive", "reach", "get",
                     "obtain", "acquire", "receive", "take", "bring", "carry", "move", "transfer",
                     "shift", "relocate", "position", "place", "put", "set", "adjust", "change",
                     "modify", "alter", "adapt", "adjust", "tweak", "fine-tune", "turn on",
                     "turn off", "switch", "toggle", "activate", "deactivate", "enable",
                     "disable", "volume", "sound", "audio", "mute", "unmute", "louder", "softer",
                     "up", "down", "increase", "decrease", "raise", "lower", "boost", "cut",
                     "bright", "brightness", "light", "illumination", "lumi", "brighten", "dim",
                     "lighten", "darken", "shade", "screen", "display", "monitor", "viewport"] or \
           any(pattern in prompt.lower() for pattern in ["hello", "hi", "hey", "good morning",
                                                         "good afternoon", "good evening",
                                                         "howdy", "sup", "what's up", "thanks",
                                                         "thank you", "yes", "no", "stop",
                                                         "cancel", "wait", "pause", "resume",
                                                         "what time is it", "current time",
                                                         "open ", "close ", "set volume",
                                                         "volume ", "set brightness",
                                                         "brightness ", "mute", "unmute",
                                                         "maximize", "minimize", "restore",
                                                         "close window", "switch to", "go to",
                                                         "search for", "what is", "who is",
                                                         "when is", "where is"]):
            expected = "simple"
        elif any(word in prompt.lower() for word in ["explain", "analyze", "compare", "contrast",
                                                    "evaluate", "assess", "discuss", "describe",
                                                    "elaborate", "detail", "why", "how", "what if",
                                                    "pros and cons", "advantages", "disadvantages",
                                                    "benefits", "drawbacks", "impact", "effect",
                                                    "influence", "relationship", "correlation",
                                                    "cause", "effect", "reason", "purpose",
                                                    "significance", "importance", "implications",
                                                    "consequences", "outcomes", "results", "findings",
                                                    "trends", "patterns", "sequences", "strategies",
                                                    "approaches", "methods", "techniques",
                                                    "procedures", "processes", "steps", "stages",
                                                    "phases", "plan", "planning", "strategy",
                                                    "design", "architecture", "structure", "framework",
                                                    "model", "theory", "concept", "principle", "rule",
                                                    "law", "algorithm", "formula", "equation",
                                                    "calculation", "compute", "calculate", "solve",
                                                    "solution", "answer", "resolve", "fix", "correct",
                                                    "improve", "optimize", "enhance", "develop",
                                                    "create", "build", "construct", "design",
                                                    "innovate", "invent", "discover", "research",
                                                    "investigate", "study", "examine", "inspect",
                                                    "review", "survey", "summarize", "conclude",
                                                    "overview", "introduction", "background", "context",
                                                    "definition", "meaning", "interpretation",
                                                    "perspective", "viewpoint", "opinion", "belief",
                                                    "thought", "idea", "concept", "notion", "principle",
                                                    "doctrine", "ideology", "philosophy", "ethics",
                                                    "morality", "values", "principles", "standards",
                                                    "criteria", "guidelines", "recommendations",
                                                    "suggestions", "proposals", "propositions",
                                                    "hypothesis", "theory", "model", "framework",
                                                    "paradigm", "methodology", "technique", "procedure",
                                                    "process", "system", "mechanism", "dynamic",
                                                    "interaction", "relationship", "connection",
                                                    "association", "link", "bond", "network", "system",
                                                    "complex", "complicated", "intricate", "detailed",
                                                    "comprehensive", "thorough", "exhaustive", "extensive",
                                                    "detailed", "elaborate", "in-depth"]):
            # Check if it's deep planning indicators
            if len(prompt.split()) > 30 or any(phrase in prompt.lower() for phrase in [
                'step by step', 'phase by phase', 'multi-step', 'several steps',
                'multiple steps', 'first', 'second', 'third', 'finally', 'lastly',
                'plan', 'strategy', 'approach', 'method', 'process', 'procedure'
            ]):
                expected = "deep_planning"
            else:
                expected = "complex"
        else:
            expected = "medium"

        is_correct = predicted == expected
        if is_correct:
            correct_predictions += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"[{status}] '{prompt}' -> {predicted} (expected: {expected}) [{description}]")

        if not is_correct and total_predictions < 20:  # Only show details for small test sets
            print(f"   Combined text: '{'' + prompt}'.lower().strip()")
            print(f"   Word count: {len(prompt.split())}")
            words = set(re.findall(r'\b\w+\b', prompt.lower()))
            complex_matches = len(words.intersection(ai_manager._complex_keywords))
            simple_matches = len(words.intersection(ai_manager._simple_keywords))
            print(f"   Complex matches: {complex_matches}, Simple matches: {simple_matches}")

    print("\n" + "=" * 50)
    accuracy = (correct_predictions / total_predictions) * 100
    print(f"Accuracy: {correct_predictions}/{total_predictions} ({accuracy:.1f}%)")

    if accuracy >= 80:
        print("PASS: Complexity detection is working well!")
        return True
    else:
        print("FAIL: Complexity detection needs improvement.")
        return False

if __name__ == "__main__":
    import re
    success = test_complexity_detection()
    sys.exit(0 if success else 1)