#!/usr/bin/env python3
"""
Catalogador de Arquivos por Tipo
Varre volumes de rede e organiza arquivos por categoria (fotos, ebooks, filmes, músicas)
"""

import os
import json
import csv
from pathlib import Path
from datetime import datetime
import hashlib
from collections import defaultdict, Counter
import shutil
import openpyxl  # Adicione este import no topo do arquivo

class FileCataloger:
    def __init__(self, verbose=False, exclude_paths=None):
        # Definir extensões por categoria
        self.categories = {
            'fotos': {
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', 
                '.webp', '.raw', '.cr2', '.nef', '.arw', '.dng', '.heic', '.heif'
            },
            'ebooks': {
                '.pdf', '.epub', '.mobi', '.azw', '.azw3', '.fb2', '.lit', 
                '.pdb', '.cbr', '.cbz'
            },
            'documents': {
                '.txt', '.rtf', '.doc', '.docx', '.xls', '.xlsx'
            },
            'filmes': {
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
                '.m4v', '.3gp', '.ogv', '.ts', '.m2ts', '.vob', '.iso'
            },
            'musicas': {
                '.mp3', '.flac', '.wav', '.aac', '.ogg', '.wma', '.m4a', 
                '.opus', '.ape', '.ac3', '.dts', '.aiff'
            },
            'outros': set()  # Para arquivos que não se encaixam nas categorias acima
        }
        
        self.catalog = defaultdict(list)
        self.stats = Counter()
        self.errors = []
        self.verbose = verbose
        self.exclude_paths = set()
        self.folders_with_files = set()  # Track folders containing matching files
        
        if exclude_paths:
            # Convert to absolute paths and normalize
            for path in exclude_paths:
                abs_path = Path(path).resolve()
                self.exclude_paths.add(abs_path)
                if self.verbose:
                    print(f"Excluindo da busca: {abs_path}")
        
        # Load folder exclusions from file if it exists
        self._load_folder_exclusions()
        
        self.operation_stats = {
            'successful_operations': 0,
            'failed_operations': 0,
            'skipped_operations': 0
        }
    
    def get_file_info(self, file_path):
        """Coleta informações detalhadas do arquivo"""
        try:
            stat = file_path.stat()
            return {
                'path': str(file_path),
                'name': file_path.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'extension': file_path.suffix.lower(),
                'parent_dir': str(file_path.parent)
            }
        except Exception as e:
            self.errors.append(f"Erro ao acessar {file_path}: {str(e)}")
            return None
    
    def get_file_hash(self, file_path, chunk_size=8192):
        """Calcula hash MD5 do arquivo (opcional, para detectar duplicatas)"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            return None
    
    def categorize_file(self, file_path):
        """Determina a categoria do arquivo baseado na extensão"""
        extension = file_path.suffix.lower()
        
        for category, extensions in self.categories.items():
            if extension in extensions:
                return category
        
        return 'outros'
    
    def scan_directory(self, directory_path, include_hash=False, max_depth=None, file_type_filter=None):
        """Varre um diretório recursivamente"""
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"Diretório não encontrado: {directory_path}")
            return
        
        if self.verbose:
            print(f"Iniciando varredura detalhada: {directory_path}")
        else:
            print(f"Varrendo: {directory_path}")
        
        try:
            # Filtrar extensões por tipo de arquivo se especificado
            target_extensions = None
            if file_type_filter and file_type_filter.lower() in self.categories:
                target_extensions = self.categories[file_type_filter.lower()]
                if self.verbose:
                    print(f"Filtrando apenas arquivos do tipo: {file_type_filter} ({len(target_extensions)} extensões)")
                    print(f"Extensões aceitas: {', '.join(sorted(target_extensions))}")
                else:
                    print(f"Filtrando apenas arquivos do tipo: {file_type_filter} ({len(target_extensions)} extensões)")
            
            # Usar rglob para busca recursiva ou glob com profundidade limitada
            if max_depth is None:
                files = directory.rglob('*')
            else:
                files = self._get_files_with_depth(directory, max_depth)
            
            for file_path in files:
                if file_path.is_file():
                    # Skip files in excluded directories
                    if self._is_path_excluded(file_path):
                        if self.verbose:
                            print(f"Excluindo arquivo: {file_path}")
                        continue
                    
                    # Skip files that don't match the filter type
                    if target_extensions and file_path.suffix.lower() not in target_extensions:
                        continue
                        
                    try:
                        # Obter informações do arquivo
                        file_info = self.get_file_info(file_path)
                        if file_info is None:
                            continue
                        
                        # Adicionar hash se solicitado
                        if include_hash:
                            file_info['hash'] = self.get_file_hash(file_path)
                        
                        # Categorizar arquivo
                        category = self.categorize_file(file_path)
                        file_info['category'] = category
                        
                        # Track folder containing this file
                        self.folders_with_files.add(str(file_path.parent))
                        
                        # Adicionar ao catálogo
                        self.catalog[category].append(file_info)
                        self.stats[category] += 1
                        self.stats['total_files'] += 1
                        self.stats['total_size'] += file_info['size']
                        
                        # Feedback de progresso
                        if self.verbose or self.stats['total_files'] % 1000 == 0:
                            if self.verbose:
                                print(f"Processando: {file_path.name} ({self.stats['total_files']} arquivos)")
                            elif self.stats['total_files'] % 1000 == 0:
                                print(f"Processados: {self.stats['total_files']} arquivos")
                            
                    except Exception as e:
                        self.errors.append(f"Erro ao processar {file_path}: {str(e)}")
                        
        except Exception as e:
            self.errors.append(f"Erro ao varrer diretório {directory_path}: {str(e)}")
    
    def _get_files_with_depth(self, directory, max_depth):
        """Busca arquivos com profundidade limitada"""
        for root, dirs, files in os.walk(directory):
            # Check if current directory should be excluded
            root_path = Path(root).resolve()
            if self._is_path_excluded(root_path):
                dirs[:] = []  # Don't descend into excluded directories
                continue
                
            level = root.replace(str(directory), '').count(os.sep)
            if level >= max_depth:
                dirs[:] = []  # Não descer mais níveis
            for file in files:
                yield Path(root) / file
    
    def _is_path_excluded(self, file_path):
        """Verifica se um caminho deve ser excluído da busca"""
        if not self.exclude_paths:
            return False
            
        file_abs_path = file_path.resolve()
        
        # Check if the file or any of its parent directories are in exclude_paths
        for exclude_path in self.exclude_paths:
            try:
                # Check if file_abs_path is the same as or under exclude_path
                file_abs_path.relative_to(exclude_path)
                return True
            except ValueError:
                # file_abs_path is not under exclude_path
                continue
        
        return False
    
    def _load_folder_exclusions(self):
        """Carrega exclusões de pastas do arquivo folder_exclusions.txt"""
        exclusions_file = Path('folder_exclusions.txt')
        if exclusions_file.exists():
            try:
                with open(exclusions_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                excluded_count = 0
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines and comments
                        try:
                            abs_path = Path(line).resolve()
                            self.exclude_paths.add(abs_path)
                            excluded_count += 1
                            if self.verbose:
                                print(f"Exclusão carregada do arquivo: {abs_path}")
                        except Exception as e:
                            error_msg = f"Erro ao processar linha de exclusão '{line}': {e}"
                            self.errors.append(error_msg)
                            if self.verbose:
                                print(f"⚠️  {error_msg}")
                
                if excluded_count > 0:
                    print(f"Carregadas {excluded_count} exclusões de pastas do arquivo folder_exclusions.txt")
                    
            except Exception as e:
                error_msg = f"Erro ao ler arquivo folder_exclusions.txt: {e}"
                self.errors.append(error_msg)
                print(f"⚠️  {error_msg}")
    
    def save_folders_list(self, output_file='folders_with_files.txt', file_type_filter=None):
        """Salva lista de pastas que contêm arquivos no escopo"""
        if not self.folders_with_files:
            print("Nenhuma pasta com arquivos encontrada para salvar.")
            return
        
        # Sort folders for better readability
        sorted_folders = sorted(self.folders_with_files)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Lista de pastas contendo arquivos no escopo\n")
                f.write(f"# Gerado em: {datetime.now().isoformat()}\n")
                if file_type_filter:
                    f.write(f"# Filtro aplicado: {file_type_filter}\n")
                f.write(f"# Total de pastas: {len(sorted_folders)}\n")
                f.write(f"#\n")
                f.write(f"# Para excluir uma pasta da busca real, copie a linha para folder_exclusions.txt\n")
                f.write(f"#\n\n")
                
                for folder in sorted_folders:
                    f.write(f"{folder}\n")
            
            print(f"Lista de pastas salva em: {output_file} ({len(sorted_folders)} pastas)")
            
        except Exception as e:
            error_msg = f"Erro ao salvar lista de pastas: {e}"
            self.errors.append(error_msg)
            print(f"⚠️  {error_msg}")
    
    def scan_multiple_volumes(self, volume_paths, include_hash=False, max_depth=None, file_type_filter=None):
        """Varre múltiplos volumes de rede"""
        print("Iniciando varredura de múltiplos volumes...")
        
        for volume_path in volume_paths:
            print(f"\n{'='*50}")
            print(f"Volume: {volume_path}")
            print(f"{'='*50}")
            
            self.scan_directory(volume_path, include_hash, max_depth, file_type_filter)
    
    def save_catalog(self, output_file='catalog.json'):
        """Salva o catálogo em arquivo JSON"""
        catalog_data = {
            'timestamp': datetime.now().isoformat(),
            'stats': dict(self.stats),
            'catalog': dict(self.catalog),
            'errors': self.errors
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog_data, f, indent=2, ensure_ascii=False)
        
        print(f"Catálogo salvo em: {output_file}")
    
    def save_catalog_csv(self, output_file='catalog.csv', delimiter='|'):
        """Salva o catálogo em formato CSV"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=delimiter)
            
            # Cabeçalho
            writer.writerow(['Category', 'Name', 'Path', 'Size', 'Extension', 
                           'Modified', 'Created', 'Parent_Dir', 'Hash'])
            
            # Dados
            for category, files in self.catalog.items():
                for file_info in files:
                    writer.writerow([
                        category,
                        file_info['name'],
                        file_info['path'],
                        file_info['size'],
                        file_info['extension'],
                        file_info['modified'],
                        file_info['created'],
                        file_info['parent_dir'],
                        file_info.get('hash', '')
                    ])
        
        print(f"Catálogo CSV salvo em: {output_file}")
    
    def save_catalog_excel(self, output_file='catalog.xlsx'):
        """Salva o catálogo em formato Excel (.xlsx)"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Catalog"

        # Cabeçalho
        headers = ['Category', 'Name', 'Path', 'Size', 'Extension', 
                   'Modified', 'Created', 'Parent_Dir', 'Hash']
        ws.append(headers)

        # Dados
        for category, files in self.catalog.items():
            for file_info in files:
                ws.append([
                    category,
                    file_info['name'],
                    file_info['path'],
                    file_info['size'],
                    file_info['extension'],
                    file_info['modified'],
                    file_info['created'],
                    file_info['parent_dir'],
                    file_info.get('hash', '')
                ])

        wb.save(output_file)
        print(f"Catálogo Excel salvo em: {output_file}")
    
    def print_summary(self):
        """Exibe resumo da catalogação"""
        print(f"\n{'='*60}")
        print("RESUMO DA CATALOGAÇÃO")
        print(f"{'='*60}")
        
        print(f"Total de arquivos: {self.stats['total_files']:,}")
        print(f"Tamanho total: {self.format_size(self.stats['total_size'])}")
        print(f"Erros encontrados: {len(self.errors)}")
        
        print(f"\nArquivos por categoria:")
        for category in ['fotos', 'musicas', 'filmes', 'ebooks', 'documents', 'outros']:
            count = self.stats[category]
            if count > 0:
                size = sum(f['size'] for f in self.catalog[category])
                print(f"  {category.title()}: {count:,} arquivos ({self.format_size(size)})")
    
    def format_size(self, size_bytes):
        """Formata tamanho em bytes para formato legível"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def organize_files(self, base_output_dir, copy_files=False, dry_run=True, file_type_filter=None, move_to_dir=None):
        """Organiza arquivos em pastas por categoria ou move para diretório específico"""
        # Reset operation stats
        self.operation_stats = {
            'successful_operations': 0,
            'failed_operations': 0,
            'skipped_operations': 0
        }
        
        # Use move_to_dir if provided, otherwise use base_output_dir
        if move_to_dir:
            base_path = Path(move_to_dir)
        else:
            base_path = Path(base_output_dir)
        
        if dry_run:
            print("MODO SIMULAÇÃO - Nenhum arquivo será movido/copiado")
        
        if move_to_dir:
            print(f"\nMovendo arquivos para: {move_to_dir}")
        else:
            print(f"\nOrganizando arquivos em: {base_output_dir}")
        
        # Filtrar por tipo de arquivo se especificado
        categories_to_process = self.catalog.items()
        if file_type_filter:
            if file_type_filter.lower() in self.categories:
                categories_to_process = [(file_type_filter.lower(), self.catalog[file_type_filter.lower()])]
                print(f"Filtrando apenas arquivos do tipo: {file_type_filter}")
            else:
                print(f"Tipo de arquivo '{file_type_filter}' não reconhecido. Tipos válidos: {', '.join(self.categories.keys())}")
                return
        
        total_files = sum(len(files) for _, files in categories_to_process)
        processed_files = 0
        
        if self.verbose:
            print(f"\nIniciando processamento de {total_files} arquivos...")
        
        for category, files in categories_to_process:
            if not files:
                continue
                
            # If using move_to_dir, put all files directly in that directory
            if move_to_dir:
                category_dir = base_path
            else:
                category_dir = base_path / category
            
            # Create directory with error handling
            if not dry_run:
                try:
                    category_dir.mkdir(parents=True, exist_ok=True)
                    if self.verbose:
                        print(f"Diretório criado/verificado: {category_dir}")
                except PermissionError as e:
                    error_msg = f"Erro de permissão ao criar diretório {category_dir}: {e}"
                    print(f"✗ {error_msg}")
                    self.errors.append(error_msg)
                    continue
                except OSError as e:
                    error_msg = f"Erro do sistema ao criar diretório {category_dir}: {e}"
                    print(f"✗ {error_msg}")
                    self.errors.append(error_msg)
                    continue
            
            print(f"\n{category.title()}: {len(files)} arquivos")
            
            # Process all files, not just first 5
            files_to_show = files if self.verbose else files[:5]
            
            for i, file_info in enumerate(files):
                src_path = Path(file_info['path'])
                
                # Check if source file still exists
                if not src_path.exists():
                    error_msg = f"Arquivo fonte não encontrado: {src_path}"
                    if i < len(files_to_show):
                        print(f"  ✗ {error_msg}")
                    self.errors.append(error_msg)
                    self.operation_stats['failed_operations'] += 1
                    processed_files += 1
                    continue
                
                dst_path = category_dir / src_path.name
                
                # Handle duplicate names with error handling
                counter = 1
                original_dst_path = dst_path
                while dst_path.exists() and not dry_run:
                    try:
                        stem = src_path.stem
                        suffix = src_path.suffix
                        dst_path = category_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                    except Exception as e:
                        error_msg = f"Erro ao gerar nome único para {src_path.name}: {e}"
                        if i < len(files_to_show):
                            print(f"  ✗ {error_msg}")
                        self.errors.append(error_msg)
                        self.operation_stats['failed_operations'] += 1
                        processed_files += 1
                        break
                else:
                    # File processing
                    if dry_run:
                        action = "COPIAR" if copy_files else "MOVER"
                        if i < len(files_to_show):
                            print(f"  {action}: {src_path} -> {dst_path}")
                        self.operation_stats['successful_operations'] += 1
                    else:
                        success = self._process_file(src_path, dst_path, copy_files, i < len(files_to_show))
                        if success:
                            self.operation_stats['successful_operations'] += 1
                        else:
                            self.operation_stats['failed_operations'] += 1
                    
                    processed_files += 1
                    
                    # Progress update for verbose mode
                    if self.verbose and processed_files % 100 == 0:
                        progress = (processed_files / total_files) * 100
                        print(f"  Progresso: {processed_files}/{total_files} ({progress:.1f}%)")
            
            if not self.verbose and len(files) > 5:
                remaining = len(files) - 5
                success_count = min(5, self.operation_stats['successful_operations'])
                print(f"  ... e mais {remaining} arquivos (processados silenciosamente)")
        
        # Print operation summary
        self._print_operation_summary()
    
    def _process_file(self, src_path, dst_path, copy_files, show_output=True):
        """Process a single file with comprehensive error handling"""
        try:
            # Check available space (basic check)
            if not copy_files:
                # For move operations, check if we have write permissions
                if not os.access(src_path.parent, os.W_OK):
                    error_msg = f"Sem permissão de escrita no diretório fonte: {src_path.parent}"
                    if show_output:
                        print(f"  ✗ {error_msg}")
                    self.errors.append(error_msg)
                    return False
            
            # Check destination directory permissions
            if not os.access(dst_path.parent, os.W_OK):
                error_msg = f"Sem permissão de escrita no diretório destino: {dst_path.parent}"
                if show_output:
                    print(f"  ✗ {error_msg}")
                self.errors.append(error_msg)
                return False
            
            # Perform the operation
            if copy_files:
                if self.verbose and show_output:
                    print(f"  Copiando: {src_path.name} -> {dst_path}")
                shutil.copy2(src_path, dst_path)
                action_word = "copiado"
            else:
                if self.verbose and show_output:
                    print(f"  Movendo: {src_path.name} -> {dst_path}")
                shutil.move(str(src_path), str(dst_path))
                action_word = "movido"
            
            if show_output:
                print(f"  ✓ {src_path.name} {action_word} com sucesso")
            
            return True
            
        except PermissionError as e:
            error_msg = f"Erro de permissão ao processar {src_path.name}: {e}"
            if show_output:
                print(f"  ✗ {error_msg}")
            self.errors.append(error_msg)
            return False
            
        except FileNotFoundError as e:
            error_msg = f"Arquivo não encontrado {src_path.name}: {e}"
            if show_output:
                print(f"  ✗ {error_msg}")
            self.errors.append(error_msg)
            return False
            
        except OSError as e:
            if e.errno == 28:  # No space left on device
                error_msg = f"Espaço insuficiente em disco para {src_path.name}: {e}"
            elif e.errno == 36:  # File name too long
                error_msg = f"Nome de arquivo muito longo {src_path.name}: {e}"
            else:
                error_msg = f"Erro do sistema ao processar {src_path.name}: {e}"
            
            if show_output:
                print(f"  ✗ {error_msg}")
            self.errors.append(error_msg)
            return False
            
        except Exception as e:
            error_msg = f"Erro inesperado ao processar {src_path.name}: {e}"
            if show_output:
                print(f"  ✗ {error_msg}")
            self.errors.append(error_msg)
            return False
    
    def _print_operation_summary(self):
        """Print summary of file operations"""
        print(f"\n{'='*50}")
        print("RESUMO DAS OPERAÇÕES")
        print(f"{'='*50}")
        print(f"Operações bem-sucedidas: {self.operation_stats['successful_operations']}")
        print(f"Operações falharam: {self.operation_stats['failed_operations']}")
        print(f"Operações ignoradas: {self.operation_stats['skipped_operations']}")
        
        if self.operation_stats['failed_operations'] > 0:
            print(f"\nErros encontrados durante as operações: {len(self.errors)}")
            if self.verbose and self.errors:
                print("\nÚltimos erros:")
                for error in self.errors[-5:]:  # Show last 5 errors
                    print(f"  - {error}")

def main():
    """Função principal"""
    import argparse
    
    # Configurar argumentos da linha de comando
    parser = argparse.ArgumentParser(
        description='Catalogador de Arquivos por Tipo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python file_cataloger.py /Volumes/Drive1 /Volumes/Drive2 --organize --no-dry-run --move --verbose
  python file_cataloger.py "C:\\NetworkDrive" --include-hash --max-depth 5 --verbose
  python file_cataloger.py /home/user/files --organize --output-dir /home/user/organized -v
        """
    )
    
    # Volumes (obrigatório, múltiplos valores)
    parser.add_argument('volumes', nargs='+', 
                       help='Caminhos dos volumes/diretórios para catalogar')
    
    # Opções de varredura
    parser.add_argument('--include-hash', action='store_true',
                       help='Calcular hash MD5 dos arquivos (útil para detectar duplicatas)')
    parser.add_argument('--max-depth', type=int, default=None,
                       help='Profundidade máxima para varrer diretórios (None = sem limite)')
    
    # Opções de organização
    parser.add_argument('--organize', action='store_true',
                       help='Organizar arquivos em pastas por categoria após catalogar')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Diretório base para organizar arquivos (padrão: organized_files_TIMESTAMP)')
    parser.add_argument('--move', action='store_true',
                       help='Mover arquivos em vez de copiar (padrão: copiar)')
    parser.add_argument('--no-dry-run', action='store_true',
                       help='Executar organização de fato (padrão: modo simulação)')
    parser.add_argument('--file-type', type=str, default=None,
                       help='Mover apenas arquivos de um tipo específico (fotos, filmes, musicas, ebooks, documents, outros)')
    parser.add_argument('--move-to', type=str, default=None,
                       help='Caminho completo onde copiar os arquivos encontrados (formato: /Volume/Path)')
    
    # Opções de output
    parser.add_argument('--no-json', action='store_true',
                       help='Não salvar arquivo JSON')
    parser.add_argument('--no-csv', action='store_true',
                       help='Não salvar arquivo CSV')
    parser.add_argument('--output-prefix', type=str, default='catalog',
                       help='Prefixo para arquivos de saída (padrão: catalog)')
    
    # Adicionar argumento para modo verboso
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Modo verboso - exibe detalhes de cada operação')
    
    args = parser.parse_args()
    
    # Prepare exclude paths list
    exclude_paths = []
    if args.move_to:
        exclude_paths.append(args.move_to)
    if args.output_dir:
        exclude_paths.append(args.output_dir)
    
    cataloger = FileCataloger(verbose=args.verbose, exclude_paths=exclude_paths)
    
    print("Catalogador de Arquivos por Tipo")
    print("================================")
    print(f"Volumes a serem processados: {len(args.volumes)}")
    for i, volume in enumerate(args.volumes, 1):
        print(f"  {i}. {volume}")
    print()
    
    # Varrer volumes
    cataloger.scan_multiple_volumes(
        args.volumes, 
        include_hash=args.include_hash,
        max_depth=args.max_depth,
        file_type_filter=args.file_type
    )
    
    # Exibir resumo
    cataloger.print_summary()
    
    # Salvar catálogos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if not args.no_json:
        json_file = f'{args.output_prefix}_{timestamp}.json'
        cataloger.save_catalog(json_file)
    
    if not args.no_csv:
        excel_file = f'{args.output_prefix}_{timestamp}.xlsx'
        cataloger.save_catalog_excel(excel_file)
    
    # Save folders list (always generate, useful for analysis)
    folders_file = f'folders_with_files_{timestamp}.txt'
    cataloger.save_folders_list(folders_file, args.file_type)
    
    # Organizar arquivos se solicitado
    if args.organize:
        output_dir = args.output_dir or f"organized_files_{timestamp}"
        dry_run = not args.no_dry_run
        copy_files = not args.move
        
        print(f"\nConfiguração da organização:")
        print(f"  Diretório de saída: {output_dir}")
        print(f"  Modo: {'SIMULAÇÃO' if dry_run else 'EXECUÇÃO REAL'}")
        print(f"  Ação: {'COPIAR' if copy_files else 'MOVER'}")
        print(f"  Modo verboso: {'ATIVADO' if args.verbose else 'DESATIVADO'}")
        
        if dry_run:
            print(f"\n💡 Dica: Revise o arquivo {folders_file} e adicione pastas indesejadas ao folder_exclusions.txt antes da execução real.")
        
        cataloger.organize_files(
            output_dir, 
            copy_files=copy_files,
            dry_run=dry_run,
            file_type_filter=args.file_type,
            move_to_dir=args.move_to
        )

if __name__ == "__main__":
    main()