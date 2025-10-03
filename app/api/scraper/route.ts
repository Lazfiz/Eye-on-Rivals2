import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

export async function POST(request: NextRequest) {
  try {
    const projectRoot = process.cwd()
    const backendPath = path.join(projectRoot, 'backend')
    const venvPath = path.join(backendPath, '.venv', 'Scripts', 'python.exe')
    
    // Try different Python commands and paths, including virtual environment
    const pythonCommands = [
      venvPath,
      path.join(backendPath, '.venv', 'Scripts', 'python.exe'),
      'backend\\.venv\\Scripts\\python.exe',
      'backend/.venv/Scripts/python.exe',
      'backend\\.venv\\Scripts\\python',
      'backend/.venv/Scripts/python',
      'python',
      'python3',
      'py',
      'python.exe',
      'python3.exe'
    ]
    
    let lastError: any = null
    
    for (const pythonCmd of pythonCommands) {
      try {
        console.log(`Trying ${pythonCmd}...`)
        
        // First check if Python is available
        const versionCheck = await execAsync(`"${pythonCmd}" --version`, {
          cwd: projectRoot,
          timeout: 10000,
          encoding: 'utf8'
        } as any)
        console.log(`Python version: ${versionCheck.stdout}`)
        
        // Try to run the scraper
        const { stdout, stderr } = await execAsync(
          `"${pythonCmd}" scraper_tool/ScraperRunner.py`,
          {
            cwd: backendPath,
            timeout: 300000, // 5 minutes timeout
            encoding: 'utf8',
            env: {
              ...process.env,
              PYTHONPATH: backendPath
            }
          } as any
        )

        if (stderr) {
          console.error('Scraper stderr:', stderr)
        }

        console.log('Scraper stdout:', stdout)

        return NextResponse.json({
          success: true,
          message: 'Scraper completed successfully',
          output: stdout,
          pythonCommand: pythonCmd
        })
        
      } catch (error) {
        console.log(`Failed with ${pythonCmd}:`, error)
        lastError = error
        continue
      }
    }
    
    // If all Python commands failed, provide more detailed error
    const errorMsg = lastError instanceof Error ? lastError.message : 'Unknown error'
    console.error('All Python commands failed:', lastError)
    
    return NextResponse.json({
      success: false,
      message: 'Python not found or scraper failed to run',
      error: errorMsg,
      details: `Tried paths: ${pythonCommands.join(', ')}. Please ensure the virtual environment exists at ${venvPath} or Python is installed and accessible in PATH.`
    }, { status: 500 })
    
  } catch (error) {
    console.error('Unexpected error:', error)
    return NextResponse.json({
      success: false,
      message: 'Unexpected error occurred',
      error: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 })
  }
}