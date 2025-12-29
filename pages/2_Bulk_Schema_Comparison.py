import streamlit as st
import pandas as pd
from deepdiff import DeepDiff
import json
from auth import HypatosAPI
from helpers import get_datapoints_dict, get_metadata

st.set_page_config(page_title="2_Bulk Schema Comparison", layout="wide")

st.title("📊 Bulk Schema Comparison")
st.markdown("---")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'source_api' not in st.session_state:
    st.session_state.source_api = None
if 'target_api' not in st.session_state:
    st.session_state.target_api = None
if 'comparison_results' not in st.session_state:
    st.session_state.comparison_results = None

# Authentication Section
st.header("🔐 Authentication")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Source Company")
    source_url = st.text_input("Source URL", key="bulk_source_url")
    source_username = st.text_input("Source Username", key="bulk_source_username")
    source_password = st.text_input("Source Password", type="password", key="bulk_source_password")

with col2:
    st.subheader("Target Company")
    target_url = st.text_input("Target URL", key="bulk_target_url")
    target_username = st.text_input("Target Username", key="bulk_target_username")
    target_password = st.text_input("Target Password", type="password", key="bulk_target_password")

if st.button("🔑 Authenticate Credentials", type="primary"):
    try:
        with st.spinner("Authenticating..."):
            source_api = HypatosAPI(source_url, source_username, source_password)
            target_api = HypatosAPI(target_url, target_username, target_password)
            
            st.session_state.source_api = source_api
            st.session_state.target_api = target_api
            st.session_state.authenticated = True
            
            st.success("✅ Authentication successful!")
    except Exception as e:
        st.error(f"❌ Authentication failed: {str(e)}")
        st.session_state.authenticated = False

st.markdown("---")

# File Upload and Comparison Section
if st.session_state.authenticated:
    st.header("📁 Upload Project Pairs")
    
    st.info("""
    **File Format Requirements:**
    - Upload an Excel (.xlsx, .xls) or CSV (.csv) file
    - **Column 1:** Source Project IDs
    - **Column 2:** Target Project IDs
    - Each row represents one comparison pair
    """)
    
    uploaded_file = st.file_uploader(
        "Choose a file", 
        type=['csv', 'xlsx', 'xls'],
        help="Upload a file with Source and Target project IDs in two columns"
    )
    
    if uploaded_file is not None:
        try:
            # Read the file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Display the uploaded data
            st.subheader("📋 Uploaded Project Pairs")
            
            # Ensure we have at least 2 columns
            if df.shape[1] < 2:
                st.error("❌ File must have at least 2 columns (Source and Target project IDs)")
            else:
                # Use first two columns regardless of their names
                df_display = df.iloc[:, :2].copy()
                df_display.columns = ['Source Project ID', 'Target Project ID']
                
                # Remove any rows with missing values
                df_display = df_display.dropna()
                
                st.dataframe(df_display, use_container_width=True)
                st.caption(f"Total pairs to compare: {len(df_display)}")
                
                # Comparison type selection
                comparison_type = st.radio(
                    "Select Comparison Type:",
                    ["Data Points", "Metadata"],
                    horizontal=True
                )
                
                # Compare button
                if st.button("🔍 Compare All Pairs", type="primary"):
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_pairs = len(df_display)
                    
                    for idx, row in df_display.iterrows():
                        source_project_id = str(row['Source Project ID']).strip()
                        target_project_id = str(row['Target Project ID']).strip()
                        
                        status_text.text(f"Comparing pair {idx + 1}/{total_pairs}: {source_project_id} → {target_project_id}")
                        
                        try:
                            if comparison_type == "Data Points":
                                # Get datapoints for both projects
                                source_datapoints = get_datapoints_dict(
                                    st.session_state.source_api, 
                                    source_project_id
                                )
                                target_datapoints = get_datapoints_dict(
                                    st.session_state.target_api, 
                                    target_project_id
                                )
                                
                                # Compare
                                diff = DeepDiff(source_datapoints, target_datapoints, ignore_order=True)
                                
                            else:  # Metadata
                                # Get metadata for both projects
                                source_metadata = get_metadata(
                                    st.session_state.source_api, 
                                    source_project_id
                                )
                                target_metadata = get_metadata(
                                    st.session_state.target_api, 
                                    target_project_id
                                )
                                
                                # Compare
                                diff = DeepDiff(source_metadata, target_metadata, ignore_order=True)
                            
                            results.append({
                                'source_project_id': source_project_id,
                                'target_project_id': target_project_id,
                                'has_differences': bool(diff),
                                'diff': diff,
                                'error': None
                            })
                            
                        except Exception as e:
                            results.append({
                                'source_project_id': source_project_id,
                                'target_project_id': target_project_id,
                                'has_differences': None,
                                'diff': None,
                                'error': str(e)
                            })
                        
                        progress_bar.progress((idx + 1) / total_pairs)
                    
                    status_text.text("✅ Comparison complete!")
                    st.session_state.comparison_results = {
                        'results': results,
                        'comparison_type': comparison_type
                    }
        
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")

    st.markdown("---")
    
    # Display Results
    if st.session_state.comparison_results is not None:
        st.header("📊 Comparison Results")
        
        results = st.session_state.comparison_results['results']
        comparison_type = st.session_state.comparison_results['comparison_type']
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        total = len(results)
        successful = len([r for r in results if r['error'] is None])
        with_differences = len([r for r in results if r['has_differences'] == True])
        identical = len([r for r in results if r['has_differences'] == False])
        
        col1.metric("Total Comparisons", total)
        col2.metric("With Differences", with_differences)
        col3.metric("Identical", identical)
        
        if successful < total:
            st.warning(f"⚠️ {total - successful} comparison(s) failed")
        
        st.markdown("---")
        
        # Detailed results for each pair
        for idx, result in enumerate(results):
            with st.expander(
                f"**Pair {idx + 1}:** {result['source_project_id']} → {result['target_project_id']}" +
                (f" ({'Identical ✅' if result['has_differences'] == False else 'Differences Found ⚠️'})" if result['error'] is None else " (Error ❌)")
            ):
                if result['error']:
                    st.error(f"Error during comparison: {result['error']}")
                else:
                    col1, col2 = st.columns(2)
                    col1.markdown(f"**Source Project:** `{result['source_project_id']}`")
                    col2.markdown(f"**Target Project:** `{result['target_project_id']}`")
                    
                    if not result['has_differences']:
                        st.success(f"✅ The {comparison_type.lower()} are identical!")
                    else:
                        st.warning(f"⚠️ Differences found in {comparison_type.lower()}")
                        
                        diff = result['diff']
                        
                        # Display different types of changes
                        if 'values_changed' in diff:
                            st.subheader("📝 Values Changed")
                            st.json(diff['values_changed'])
                        
                        if 'dictionary_item_added' in diff:
                            st.subheader("➕ Items Added in Target")
                            st.json(diff['dictionary_item_added'])
                        
                        if 'dictionary_item_removed' in diff:
                            st.subheader("➖ Items Removed from Target")
                            st.json(diff['dictionary_item_removed'])
                        
                        if 'iterable_item_added' in diff:
                            st.subheader("➕ List Items Added")
                            st.json(diff['iterable_item_added'])
                        
                        if 'iterable_item_removed' in diff:
                            st.subheader("➖ List Items Removed")
                            st.json(diff['iterable_item_removed'])
                        
                        if 'type_changes' in diff:
                            st.subheader("🔄 Type Changes")
                            st.json(diff['type_changes'])
                        
                        # Show full diff in expandable section
                        with st.expander("🔍 View Complete Diff Details"):
                            st.json(diff)
        
        # Export results option
        st.markdown("---")
        st.subheader("💾 Export Results")
        
        # Create summary dataframe
        summary_data = []
        for result in results:
            summary_data.append({
                'Source Project ID': result['source_project_id'],
                'Target Project ID': result['target_project_id'],
                'Status': 'Error' if result['error'] else ('Identical' if not result['has_differences'] else 'Differences Found'),
                'Error Message': result['error'] if result['error'] else ''
            })
        
        summary_df = pd.DataFrame(summary_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = summary_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Summary (CSV)",
                data=csv,
                file_name="schema_comparison_summary.csv",
                mime="text/csv"
            )
        
        with col2:
            # Create detailed JSON export
            detailed_export = {
                'comparison_type': comparison_type,
                'total_comparisons': total,
                'successful_comparisons': successful,
                'with_differences': with_differences,
                'identical': identical,
                'results': [
                    {
                        'source_project_id': r['source_project_id'],
                        'target_project_id': r['target_project_id'],
                        'has_differences': r['has_differences'],
                        'error': r['error'],
                        'diff': r['diff'].to_dict() if r['diff'] else None
                    }
                    for r in results
                ]
            }
            
            json_str = json.dumps(detailed_export, indent=2, default=str)
            st.download_button(
                label="📥 Download Detailed Results (JSON)",
                data=json_str,
                file_name="schema_comparison_detailed.json",
                mime="application/json"
            )

else:
    st.info("👆 Please authenticate with both source and target company credentials to continue.")
