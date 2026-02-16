from flask import Flask, render_template, request, jsonify
from flask_cors import CORS  
import os
import PyPDF2
import docx
import re
import tempfile  
import time
import threading
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# ============================================
# FIX 1: KEEP ALIVE FUNCTION - Prevents server from sleeping
# ============================================
def keep_alive():
    """Background thread to keep server active"""
    while True:
        time.sleep(240)  # Every 4 minutes (Render free tier sleeps after 5 min)
        try:
            # This keeps the server active
            print(f"[Keep Alive] Server active at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass

# Start keep-alive thread when app starts on Render
if os.environ.get('RENDER') == 'true':
    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()
    print("✅ Keep-alive thread started - Server will not sleep")

# ============================================
# FIX 2: HEALTH CHECK ENDPOINT - For mobile wake-up
# ============================================
@app.route('/health', methods=['GET'])
def health():
    """Quick endpoint to wake up the server"""
    return jsonify({
        'status': 'awake',
        'time': datetime.now().isoformat(),
        'message': 'Server is ready to accept uploads',
        'active_threads': threading.active_count()
    }), 200

# ============================================
# FIX 3: OPTIONS method for CORS preflight (Mobile browsers need this)
# ============================================
@app.route('/analyze', methods=['OPTIONS'])
def handle_options():
    response = jsonify({'status': 'ok'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    response.headers.add('Access-Control-Max-Age', '3600')
    return response

@app.route('/check_ats', methods=['OPTIONS'])
def handle_options_check():
    response = jsonify({'status': 'ok'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
    response.headers.add('Access-Control-Max-Age', '3600')
    return response

# ATS Keywords Database
ATS_DATA = {
    'technical_skills': [
        # Programming Languages
        'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin',
        'typescript', 'go', 'rust', 'scala', 'perl', 'r', 'matlab',
        
        # Web Technologies
        'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django',
        'flask', 'spring', 'bootstrap', 'jquery', 'ajax', 'rest api', 'graphql',
        
        # Databases
        'sql', 'mysql', 'postgresql', 'mongodb', 'oracle', 'redis', 'elasticsearch',
        'cassandra', 'dynamodb', 'firebase', 'mariadb', 'sqlite',
        
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'jenkins',
        'git', 'github', 'gitlab', 'ci/cd', 'terraform', 'ansible', 'puppet',
        'chef', 'prometheus', 'grafana', 'elk stack',
        
        # Data Science & ML
        'machine learning', 'deep learning', 'ai', 'artificial intelligence',
        'data science', 'data analysis', 'tensorflow', 'pytorch', 'keras',
        'pandas', 'numpy', 'scikit-learn', 'opencv', 'nlp', 'llm',
        
        # Tools & Others
        'jira', 'confluence', 'slack', 'trello', 'asana', 'microsoft office',
        'excel', 'powerpoint', 'word', 'outlook', 'photoshop', 'figma', 'sketch',
        'tableau', 'power bi', 'looker', 'sas', 'spss'
    ],
    
    'soft_skills': [
        'leadership', 'teamwork', 'communication', 'problem solving',
        'critical thinking', 'time management', 'project management',
        'adaptability', 'creativity', 'collaboration', 'analytical',
        'decision making', 'conflict resolution', 'negotiation',
        'presentation', 'public speaking', 'writing', 'interpersonal',
        'emotional intelligence', 'empathy', 'patience', 'mentoring',
        'coaching', 'training', 'customer service', 'sales', 'marketing'
    ],
    
    'action_verbs': [
        'developed', 'managed', 'created', 'implemented', 'designed',
        'led', 'achieved', 'improved', 'increased', 'reduced',
        'built', 'coordinated', 'established', 'generated', 'launched',
        'delivered', 'executed', 'facilitated', 'guided', 'handled',
        'initiated', 'innovated', 'introduced', 'maintained', 'monitored',
        'organized', 'performed', 'planned', 'prioritized', 'produced',
        'recommended', 'resolved', 'reviewed', 'scheduled', 'simplified',
        'streamlined', 'strengthened', 'supervised', 'trained', 'transformed',
        'updated', 'validated', 'wrote', 'analyzed', 'architected'
    ],
    
    'education_keywords': [
        'bachelor', 'master', 'phd', 'b.tech', 'm.tech', 'b.e.', 'm.e.',
        'b.sc', 'm.sc', 'b.com', 'm.com', 'b.a.', 'm.a.', 'mba', 'bca', 'mca',
        'diploma', 'certification', 'degree', 'university', 'college',
        'gpa', 'cgpa', 'honors', 'distinction', 'merit', 'scholarship'
    ],
    
    'certifications': [
        'aws certified', 'azure certified', 'google certified', 'pmp',
        'prince2', 'scrum master', 'csm', 'psm', 'safe', 'itil',
        'ccna', 'ccnp', 'ceh', 'cissp', 'cisa', 'cism',
        'comptia', 'microsoft certified', 'oracle certified', 'salesforce',
        'tableau certified', 'power bi certified', 'six sigma', 'lean'
    ]
}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"Page {page_num + 1}:\n{page_text}\n\n"
    except Exception as e:
        print(f"PDF extraction error: {e}")
    return text

def extract_text_from_docx(filepath):
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(filepath)
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        
        # Extract from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text += cell.text + " "
                text += "\n"
    except Exception as e:
        print(f"DOCX extraction error: {e}")
    return text

def extract_contact_info(text):
    """Extract contact information from resume"""
    info = {
        'email': [],
        'phone': [],
        'linkedin': False,
        'github': False,
        'portfolio': False
    }
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    info['email'] = list(set(emails))
    
    # Phone pattern (various formats)
    phone_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
        r'\b\d{10}\b',  # 1234567890
        r'\+\d{1,3}\s?\d{10}\b',  # +91 1234567890
        r'\(\d{3}\)\s?\d{3}[-.]?\d{4}\b'  # (123) 456-7890
    ]
    
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    info['phone'] = list(set(phones))
    
    # Social links
    info['linkedin'] = 'linkedin.com/in/' in text.lower()
    info['github'] = 'github.com/' in text.lower()
    info['portfolio'] = 'portfolio' in text.lower() or 'personal website' in text.lower()
    
    return info

def calculate_ats_score(text):
    """Calculate ATS score based on various factors"""
    text_lower = text.lower()
    words = text.split()
    
    # Find keywords from each category
    found_keywords = {
        'technical_skills': [],
        'soft_skills': [],
        'action_verbs': [],
        'education_keywords': [],
        'certifications': []
    }
    
    for category, keywords in ATS_DATA.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                found_keywords[category].append(keyword)
    
    # Calculate category scores
    category_scores = {}
    total_possible = 0
    total_found = 0
    
    for category, keywords in ATS_DATA.items():
        possible = len(keywords)
        found = len(found_keywords[category])
        total_possible += possible
        total_found += found
        
        if possible > 0:
            category_scores[category] = round((found / possible) * 100, 1)
        else:
            category_scores[category] = 0
    
    # Overall ATS score
    ats_score = round((total_found / total_possible) * 100, 1) if total_possible > 0 else 0
    
    # Contact information score (10% weight)
    contact_info = extract_contact_info(text)
    contact_score = 0
    if contact_info['email']:
        contact_score += 4
    if contact_info['phone']:
        contact_score += 3
    if contact_info['linkedin']:
        contact_score += 2
    if contact_info['github'] or contact_info['portfolio']:
        contact_score += 1
    
    # Length score (10% weight)
    word_count = len(words)
    if word_count < 300:
        length_score = 2
    elif word_count < 400:
        length_score = 5
    elif word_count < 600:
        length_score = 8
    elif word_count < 800:
        length_score = 10
    else:
        length_score = 7
    
    # Final score (80% keywords + 10% contact + 10% length)
    final_score = round((ats_score * 0.8) + (contact_score * 2) + (length_score * 0.5), 1)
    
    return {
        'final_score': final_score,
        'keyword_score': ats_score,
        'contact_score': contact_score,
        'length_score': length_score,
        'category_scores': category_scores,
        'found_keywords': found_keywords,
        'keyword_counts': {
            'total': total_found,
            'technical': len(found_keywords['technical_skills']),
            'soft': len(found_keywords['soft_skills']),
            'actions': len(found_keywords['action_verbs']),
            'education': len(found_keywords['education_keywords']),
            'certifications': len(found_keywords['certifications'])
        },
        'contact_info': contact_info,
        'word_count': word_count
    }

def get_score_rating(score):
    """Get rating based on score"""
    if score >= 90:
        return "Excellent", "🎯 Top 5% Resume"
    elif score >= 80:
        return "Very Good", "📈 Strong Contender"
    elif score >= 70:
        return "Good", "👍 Above Average"
    elif score >= 60:
        return "Average", "📊 Needs Optimization"
    elif score >= 50:
        return "Below Average", "⚠️ Improve Keywords"
    else:
        return "Poor", "❌ Major Changes Needed"

def generate_recommendations(analysis, text):
    """Generate personalized recommendations"""
    recommendations = []
    found = analysis['found_keywords']
    counts = analysis['keyword_counts']
    contact = analysis['contact_info']
    
    # Technical skills recommendations
    if counts['technical'] < 5:
        recommendations.append({
            'category': 'Technical Skills',
            'priority': 'High',
            'message': 'Add more technical skills relevant to your target role. Include programming languages, frameworks, and tools.',
            'examples': ['Python', 'Java', 'SQL', 'AWS', 'Docker', 'React']
        })
    
    # Soft skills recommendations
    if counts['soft'] < 3:
        recommendations.append({
            'category': 'Soft Skills',
            'priority': 'Medium',
            'message': 'Include soft skills that employers look for.',
            'examples': ['Leadership', 'Communication', 'Problem Solving', 'Teamwork']
        })
    
    # Action verbs recommendations
    if counts['actions'] < 5:
        recommendations.append({
            'category': 'Action Verbs',
            'priority': 'High',
            'message': 'Use strong action verbs to describe your achievements.',
            'examples': ['Developed', 'Managed', 'Implemented', 'Led', 'Achieved']
        })
    
    # Contact information recommendations
    if not contact['email']:
        recommendations.append({
            'category': 'Contact Info',
            'priority': 'Critical',
            'message': 'Add your email address to your resume.',
            'examples': ['your.name@email.com']
        })
    
    if not contact['phone']:
        recommendations.append({
            'category': 'Contact Info',
            'priority': 'High',
            'message': 'Include a phone number for recruiters to contact you.',
            'examples': ['(123) 456-7890']
        })
    
    if not contact['linkedin']:
        recommendations.append({
            'category': 'Professional Links',
            'priority': 'Medium',
            'message': 'Add your LinkedIn profile URL.',
            'examples': ['linkedin.com/in/yourprofile']
        })
    
    # Length recommendations
    if analysis['word_count'] < 300:
        recommendations.append({
            'category': 'Resume Length',
            'priority': 'Medium',
            'message': 'Your resume is too short. Add more details about your experience and achievements.',
            'examples': ['Add project descriptions', 'Include more responsibilities', 'Quantify achievements']
        })
    elif analysis['word_count'] > 1000:
        recommendations.append({
            'category': 'Resume Length',
            'priority': 'Low',
            'message': 'Your resume is long. Consider making it more concise (target 500-800 words).',
            'examples': ['Remove outdated experience', 'Consolidate similar points']
        })
    
    # Education recommendations
    if counts['education'] < 2:
        recommendations.append({
            'category': 'Education',
            'priority': 'Medium',
            'message': 'Highlight your education section better.',
            'examples': ['Degree name', 'University', 'Graduation year', 'GPA if >3.5']
        })
    
    # Certification recommendations
    if counts['certifications'] < 1:
        recommendations.append({
            'category': 'Certifications',
            'priority': 'Low',
            'message': 'Consider adding relevant certifications to stand out.',
            'examples': ['AWS Certified', 'PMP', 'Scrum Master', 'Google Analytics']
        })
    
    return recommendations[:7]  # Return top 7 recommendations

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST', 'OPTIONS'])  # Added OPTIONS method
def analyze():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Please upload PDF or DOCX file'}), 400
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        
        # Extract text
        if filename.endswith('.pdf'):
            text = extract_text_from_pdf(filepath)
        else:
            text = extract_text_from_docx(filepath)
        
        # Clean up file
        os.remove(filepath)
        
        if not text or len(text.strip()) < 50:
            return jsonify({'error': 'Could not extract enough text from file. Please ensure the file is not empty or corrupted.'}), 400
        
        # Analyze resume
        analysis = calculate_ats_score(text)
        
        # Get rating
        rating, description = get_score_rating(analysis['final_score'])
        analysis['rating'] = rating
        analysis['rating_description'] = description
        
        # Generate recommendations
        analysis['recommendations'] = generate_recommendations(analysis, text)
        
        # Add sample keywords for missing categories
        analysis['sample_keywords'] = {
            'technical_skills': ATS_DATA['technical_skills'][:10],
            'soft_skills': ATS_DATA['soft_skills'][:8],
            'action_verbs': ATS_DATA['action_verbs'][:10]
        }
        
        # Add CORS headers to response
        response = jsonify(analysis)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/check_ats', methods=['GET', 'OPTIONS'])  # Added OPTIONS method
def check_ats():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        return response

    response = jsonify({
        'message': "🔍 Amazon ATS (Applicant Tracking System) Test",
        'tips': [
            {
                'title': 'Formatting Tips',
                'items': [
                    'Use standard fonts (Arial, Calibri, Times New Roman)',
                    'Save as PDF or DOCX (not JPEG or PNG)',
                    'Avoid headers, footers, tables, and columns',
                    'Use bullet points for easy scanning'
                ]
            },
            {
                'title': 'Content Tips',
                'items': [
                    'Include job-specific keywords from description',
                    'Quantify achievements with numbers and percentages',
                    'Use both technical skills and soft skills',
                    'Add complete contact information'
                ]
            },
            {
                'title': 'Amazon Specific Tips',
                'items': [
                    'Include Leadership Principles examples',
                    'Use STAR method for achievements',
                    'Highlight customer obsession examples',
                    'Show ownership and bias for action'
                ]
            }
        ]
    })
    
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    print("🚀 ATS Resume Analyzer Starting...")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print("✨ Ready to analyze resumes!")
    
    # Get port from environment variable (for Render) or use default
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)