Prepare the video-model prompt for the attached target image.

Treat every `<empty>` value as absent and do not infer a replacement. Caption
must come from data.contents[image_id].text; if it is absent, use `<empty>` and
never fall back to block.text.

<target-image-context>
Role: {{target_role}}
Caption: {{caption}}
Current section heading: {{current_heading}}
Nearest meaningful block before: {{nearest_block_before}}
Nearest meaningful block after: {{nearest_block_after}}
First meaningful article block: {{first_meaningful_block}}
Optional user direction: {{user_direction}}
</target-image-context>

<article-data>
Title: {{title}}
Lead: {{lead}}
Full cleaned article in source order:
{{full_cleaned_article}}
</article-data>
